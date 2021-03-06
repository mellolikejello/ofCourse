"""
Author: Ryan Brown <sb@ryansb.com>
License: Apache 2.0
"""

import os

import yaml
import click
from distutils import dir_util
from distutils import file_util

from ofcourse.cli.util import year, season
from ofcourse.cli.openshift_utils import (generate_token,
                                          get_api,
                                          get_app,
                                          is_dirty,
                                          new_app,
                                          push,
                                          )
from ofcourse.version import __version__
from ofcourse.tests.test_yaml import TestAllYaml
import unittest


@click.group()
def cli():
    pass


@cli.command()
def version():
    click.echo("You are using ofcourse version {}".format(__version__))
    click.echo("Get more information at "
               "https://github.com/ryansb/ofCourse")


@cli.command(short_help="Run your course locally, and view it on "
             "http://localhost:5000")
def run():
    from ofcourse.site import app
    app.run(
        debug=True,
        threaded=True,
    )


@cli.command(short_help="Make a new course site from scratch")
def new():
    # \u2714 is a check mark
    # \u2717 is an x
    # TODO: include default README with instructions for starting your course
    click.echo(u'\u2714 Glorious README')

    source_dir = os.path.split(__file__)[0].replace('cli', '')

    static_dir = os.path.join(os.getcwd(), 'static')
    dir_util.copy_tree(source_dir + 'static', static_dir, update=True)

    click.echo(u'\u2714 CSS/Javascript for browser art')

    templates_dir = os.path.join(os.getcwd(), 'templates')
    dir_util.copy_tree(os.path.join(source_dir, '..', 'ofcourse-templates'),
                       templates_dir, update=True)

    click.echo(u'\u2714 Starter Mako templates for great good')

    yamls_dir = os.path.join(source_dir, 'yamls')

    people_dir = os.path.join(os.getcwd(), 'people', year(), season())
    if not os.path.isdir(people_dir):
        os.makedirs(people_dir)

    file_util.copy_file(os.path.join(yamls_dir, 'fake_student.yaml'),
                        people_dir, update=True)

    file_util.copy_file(os.path.join(yamls_dir, 'assignments.yaml'),
                        os.getcwd(), update=True)
    file_util.copy_file(os.path.join(yamls_dir, 'site.yaml'),
                        os.getcwd(), update=True)
    file_util.copy_file(os.path.join(yamls_dir, 'oer.yaml'),
                        os.getcwd(), update=True)
    file_util.copy_file(os.path.join(source_dir, ".travis.yml"),
                        os.getcwd(), update=True)

    click.echo(u'\u2714 Starter yaml files for data driven education')


@cli.command(short_help="Synchronize templates from ofcourse to your content" +
             " repository")
def sync():
    click.confirm('This will add (and potentially overwrite) files in your' +
                  ' course repository. The changes will not be permanent and' +
                  ' you can use git to undo anything you would rather not' +
                  ' have. Would you like to continue?', abort=True)
    module_dir = os.path.split(__file__)[0].replace('cli', '')

    templates_src = os.path.join(
        module_dir,
        '..',
        'ofcourse-templates',
    )

    templates_dest = os.path.join(os.getcwd(), 'templates')

    if not os.path.isdir(templates_dest):
        click.echo(u'\u2717 Uhoh, {} is not a directory...')
        click.echo(u'If you are trying to start a new course, try' +
                   u' `ofcourse new`')
        click.echo(u'If you are updating an existing course, make' +
                   u' sure you are in the right directory')
        click.exit(1)

    dir_util.copy_tree(templates_src, templates_dest, update=True)

    click.echo(u'\u2714 Your templates have been updated!')

    static_dest = os.path.join(os.getcwd(), 'static')

    dir_util.copy_tree(os.path.join(module_dir, 'static'),
                       static_dest, update=True)

    click.echo(u'\u2714 Your static content (CSS/JS) has been updated!')

    click.echo(u'Make sure to add the new files to your git repository')
    click.echo(u'Tip: To see what\'s new, use `git add -p` to stage changes' +
               u' individually, and `git status` to check for new files')


@cli.command(short_help="Validates ofcourse website using "
             "all of the tests currently built into ofcourse "
             "Currently these tests validate YAML files")
@click.pass_context
def validate(ctx):
    click.echo("Validating ofCourse Participant YAML Files")

    suite = unittest.TestSuite()
    suite.addTest(TestAllYaml("test_recursive_yaml"))
    suite.addTest(TestAllYaml("test_student_yaml"))

    runner = unittest.TextTestRunner()
    ctx.exit(len(runner.run(suite).failures))


@cli.command(short_help="Push this to openshift. Requires "
             "http://openshift.com account. Will check for "
             "course.openshift.git_url as well as CLI flag --remote")
@click.option("--verbose", help="Show more info", is_flag=True)
@click.option('--app', help="Openshift app name (e.g. hfoss)")
@click.option('--user', help="Openshift username (usually your email)")
@click.option('--domain', help="Openshift domainname")
def openshift(verbose, app, user, domain):
    appname = app
    site_yaml = os.path.join(os.getcwd(), 'site.yaml')

    if is_dirty():
        click.confirm(
            "You have uncommitted changes. Changes that aren't "
            "committed won't be pushed to openshift.\n"
            "Do you want to continue?", abort=True
        )
    conf = os.path.join(os.getenv("HOME"), ".ofcourse.token")
    token = None
    try:
        with open(conf, 'r') as cfg:
            token = cfg.read().strip()
        api = get_api(token)
        # The idea here is that we test out the token by listing
        # apps, and if there's a failure we just fall through to
        # asking for uname/pass
        api.app_list(domain_name=domain)
    except Exception:
        if not user:
            user = click.prompt("Openshift username")
        password = click.prompt("Openshift password", hide_input=True)
        token = generate_token(user, password)
        with open(conf, 'w') as cfg:
            cfg.write(token)

    api = get_api(token)
    if not domain:
        domain = api.domain_get()[1]

    if (not appname) and os.path.isfile(site_yaml):
        with open(site_yaml, 'r') as site:
            s = yaml.load(site)
            appname = s.get("course", {}
                            ).get("openshift", {}
                                  ).get("app_name", None)

    try:
        get_app(appname, api, domain)
    except:
        if click.confirm("The app {} could not be found, should I create it"
                         " automatically?".format(appname)):
            new_app(appname, api, domain)

    if verbose:
        click.echo("Pushing files to openshift app {}".format(appname))

    app_url = push(appname, api, domain)
    click.echo("Your app is now on Openshift at {}".format(app_url))

# Contributing to g2p

Feel free to dive in! [Open an issue](https://github.com/NRC-ILT/g2p/issues/new) or submit PRs.

This repo follows the [Contributor Covenant](http://contributor-covenant.org/version/1/3/0/) Code of Conduct.

This repo uses automated tools to standardize the formatting of code, text files and
commits.
 - [Pre-commit hooks](#pre-commit-hooks) validate and automatically apply code
   formatting rules.
 - [commitlint](#commitlint) is used as a commit message hook to validate that
   commit messages follow the convention.

To keep g2p accessible and welcoming, we don't require contributors to apply these rules
before submitting pull requests, but we will probably apply them for you before merging
them in.

## TL;DR

Please consider using the `dev` environment with `hatch` to do
development, which enables some checking of Git commits and messages:

```sh
hatch -e dev shell
```

If you have a pre-existing virtual environment (sandbox), you can also
install the required packages with `pip`:

```sh
pip install -e ".[dev]"
pre-commit install
gitlint install-hook
```

## Pre-commit hooks

The g2p team has agreed to systematically use a number of pre-commit hooks to
normalize formatting of code. You can install and enable pre-commit to have these used
automatically when you do your own commits.

Pre-commit hooks enabled:
- check-yaml validates YAML files
- end-of-file-fixer makes sure each text file ends with exactly one newline character
- trailing-whitespace removes superfluous whitespace at the end of lines in text files
- [Flake8](https://flake8.pycqa.org/) enforces good Python style rules; more info about
  using Flake8 in pre-commit hooks at:
  [Lj Miranda flake8 blog post](https://ljvmiranda921.github.io/notebook/2018/06/21/precommits-using-black-and-flake8/)
- [isort](https://pycqa.github.io/isort/) orders python imports in a standard way
- [Black](https://github.com/psf/black), the Uncompromising Code Formatter, refortmats all
  Python code according to very strict rules we've agreed to follow; more info about Black
  formatting rules in
  [The Black code style](https://black.readthedocs.io/en/stable/the_black_code_style.html)
- [mypy](http://mypy-lang.org/) runs type checking for any statically-typed Python code in
  the repo

### Enabling pre-commit hooks

All the pre-commit hooks are executed using a tool called
[pre-commit](https://pre-commit.com/). Once you enable pre-commit, it will run all the
hooks each time you try to commit anything in this repo.

We've added all the developer dependencies for the project to the
`dev` environment to make them easy to install with `hatch`.  In
addition, `pre-commit` and `gitlint` hooks will be installed on
creation of this environment.  Note that you will have to use the
`dev` environment when committing since pre-commit is installed there.
You can either start a shell:

```sh
hatch -e dev shell
```

Or run commands in the environment:

```sh
hatch -e dev run git commit -m 'chore: foo bar baz'
```

If you have a pre-existing virtual environment (sandbox), you can also
install the required packages with `pip`:

```sh
pip install -e ".[dev]"
pre-commit install
```

## commitlint

The team has also agreed to use [Conventional Commits](https://www.conventionalcommits.org/).
Install and enable [gitlint](https://jorisroovers.com/gitlint/) to have your
commit messages scanned automatically.

Convential commits look like this:

    type(optional-scope): subject (i.e., short description)

    optional body, which is free form

    optional footer

Valid types: (these are the default, which we're using as is for now)
 - build: commits for the build system
 - chore: maintain the repo, not the code itself
 - ci: commits for the continuous integration system
 - docs: adding and changing documentation
 - feat: adding a new feature
 - fix: fixing something
 - perf: improving performance
 - refactor: refactor code
 - revert: undo a previous change
 - style: working only on code or documentation style
 - test: commits for testing code

Valid scopes: the scope is optional and usually refers to which module is being changed.
 - TBD - for now not validated, should be just one word ideally

Valid subject: short, free form, what the commit is about in less than 50 or 60 characters
(not strictly enforced, but it's best to keep it short)

Optional body: this is where you put all the verbose details you want about the commit, or
nothing at all if the subject already says it all. Must be separated by a blank line from
the subject. Explain what the changes are, why you're doing them, etc, as necessary.

Optional footer: separated from the body (or subject if body is empty) by a blank line,
lists reference (e.g.: "Closes #12" "Ref #24") or warns of breaking changes (e.g.,
"BREAKING CHANGE: explanation").

These rules are inspired by these commit formatting guides:
 - [Conventional Commits](https://www.conventionalcommits.org/)
 - [Bluejava commit guide](https://github.com/bluejava/git-commit-guide)
 - [develar's commit message format](https://gist.github.com/develar/273e2eb938792cf5f86451fbac2bcd51)
 - [AngularJS Git Commit Message Conventions](https://docs.google.com/document/d/1QrDFcIiPjSLDn3EL15IJygNPiHORgU1_OOAqWjiDU5Y).

### Enabling commitlint

We run commitlint on each commit message that you write by enabling the commit-msg hook in
Git.

The commit-msg hook is enabled on creation of the `dev` environment
with `hatch`.  Note that you will have to use the `dev` environment
when committing since pre-commit is installed there.  You can either
start a shell:

```sh
hatch -e dev shell
```

Or run commands in the environment:

```sh
hatch -e dev run git commit -m 'chore: foo bar baz'
```

If you have a pre-existing virtual environment (sandbox), you can also
install the required packages with `pip`:

```sh
pip install -e ".[dev]"
gitlint install-hook
```

- Now, next time you make a change and commit it, your commit log will be checked:
  - `git commit -m'non-compliant commit log text'` outputs an error
  - `git commit -m'fix(g2p): fixing a bug in g2p integration'` works

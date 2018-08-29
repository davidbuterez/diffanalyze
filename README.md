# diffanalyze
Script to extract useful patch testing information from git repositories. Currently, it is intended for use only with C programs.

## Usage
diffanalyze has two main functionalities, which will be explained in detail:
- Output the updated functions and corresponding code lines of a patch, given a commit hash
- Look at all the commits in a repository and output histograms that relate the number of updated functions to the number of commits

The information given below can also be briefly accessed via the `--help, -h` flags.

### Updated functions
Sample usage:
`./diffanalyze.py https://git.savannah.gnu.org/git/findutils.git -hash HEAD --print-mode full`

The first argument is always required: it is the URL of the repo that is to be queried

Optional arguments:
- `-hash HASH` - this is the patch commit hash we are interested in; the script will compare this revision to the previos one and output the patch updates. It supports normal git revision features: `HEAD~`, `HEAD^3`, `ba6be28~2`, etc.
- `--print-mode` - has 3 possible values: *full*, *simple*, *only-fn*.
    - `full` - prints a human readable version, including the updated function name, source file, and newly added lines
    - `simple` - outputs the source file name and source code line number, for each newly added line in the patch
    - `only-fn` - outputs only the names of the functions that were updated in the patch, one per line
- `--verbose` - prints some additional information about what the script is doing (repo already cloned, current commit, etc.)
- `--cache, -c` - doesn't delete the cloned repository after the script finishes - useful if you want to avoid cloning each time
- `--rangeInt, -ri N` - Looks at N patches, starting from `HASH` (directions is newer -> older commits)
- `--range, -rh INIT_HASH` - Looks at patches between `HASH` (newest) and `INIT_HASH` (oldest) (inclusive, directions is newer -> older commits)

### Histogram
Sample usage:
`./diffanalyze.py https://git.savannah.gnu.org/git/findutils.git -sp`

Arguments:
- `--summary, -s` - prints a summary of the data (how many commits update N functions, how many file extensions were involved in commits, etc.)
- `--plot, -p` - saves a graph of the data given in the summary
- `--skip-initial, -i` - skip the initial commit, as it may very large and not of interest
- `--limit, -l N` - only plot the data of the first N commits (e.g. first 25 commits)
- `--rangeInt, -ri N` - same as above
- `--range, -rh INIT_HASH` - same as above

## Installation
### Ubuntu
If you are using Ubuntu, run the **setup.sh** script:
    `./setup.sh`

This will check and install any missing packages and libraries. The script was tested on a fresh install of Ubuntu 16.04 and Ubuntu 18.04, where the following will be required:

- python3
- pip3
- python3-dev
- git
- cmake
- openssl
- autoconf
- pkg-config
- libffi6 
- libffi-dev
- libssl-dev
- libjansson-dev
- libjansson4

Python also requires the following modules:
- pygit2
- matplotlib
- termcolor

These will be installed automatically by the script (pygit2 is the most problematic, if the script could not install it, it will provide a link to the official installation guide).

The default version of *ctags* that is available on Ubuntu is *Exuberant Ctags*. diffanalyze requires *Universal Ctags*, which provides additional features. The setup script will install the required version as **universalctags** (should avoid conflicts with the default one).

### Mac OS X
Tested on Mac OS X Sierra (10.12).
Make sure you have `git`,`python3` and `pip3` installed.
Assuming you have `brew` installed:
- `brew install jansson`
- `brew install libgit2`
- `pip3 install pygit2`
- `pip3 installl matplotlib`
- `pip3 install pyqt5`
- `pip3 install termcolor`
- `git clone https://github.com/universal-ctags/ctags; cd ctags; ./autogen.sh; ./configure --program-prefix=universal; make`

## Known issues
The matplotlib graphs can look weird when inspecting a small number (e.g. 4) of patches with the `--range` arguments.

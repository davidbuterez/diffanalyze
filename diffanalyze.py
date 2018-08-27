#!/usr/bin/env python3
import sys
import argparse
import os
import subprocess
import shlex
import shutil
import getpass
import pygit2
import json
import collections
import matplotlib.pyplot as plt

from matplotlib.ticker import MaxNLocator
from os.path import dirname, abspath
from io import StringIO
from termcolor import colored

GIT_EMPTY_TREE_ID = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

class OutputManager:

  should_print = False
  old_stdout = sys.stdout
  output = StringIO()
  
  @staticmethod
  def print(*args, **kwargs):
    if OutputManager.should_print:
      print(' '.join(map(str,args)), **kwargs)

  @staticmethod
  def print_diff_summary(diff_summary, pretty):
    for diff_data in diff_summary.file_diffs:
      diff_data.print(pretty)

  @staticmethod
  def print_diff_summary_simple(diff_summary):
    for diff_data in diff_summary.file_diffs:
      diff_data.print_simple()
  
  @staticmethod
  def print_relevant_diff(diff_summary, print_mode):
    if print_mode == 'simple':
      OutputManager.print_diff_summary_simple(diff_summary)
      return
    
    if print_mode == 'only-fn':
      OutputManager.print_diff_summary(diff_summary, pretty=False)
    else:
      OutputManager.print_diff_summary(diff_summary, pretty=True)
      if diff_summary.updated_fn_count == 0:
        OutputManager.print('No relevant changes detected.')
    OutputManager.print()      
  
  @staticmethod
  def print_all(only_fn):
    strs = OutputManager.output.getvalue().strip().split('\n') if not only_fn else list(dict.fromkeys(OutputManager.output.getvalue().strip().split('\n')))
    sys.stdout = OutputManager.old_stdout
    for str in strs:
      if str and str != '\n':
        print(str)

class ChangedLinesManager:

  def __init__(self, added_lines, removed_lines, patch_commit):
    self.added_lines = added_lines
    self.removed_lines = removed_lines
    self.patch_msg = 'Patch ' + patch_commit + ' has added lines'

  def print_added_lines(self):
    if self.added_lines:
      print(self.patch_msg + ' (new file indices): [', end='')
      print(*self.added_lines, end='')
      print(']')

  def print_removed_lines(self):
    if self.removed_lines:
      print(self.patch_msg + ' (old file indices): [', end='')
      print(*self.removed_lines, end='')
      print(']')

class FnAttributes:

  def __init__(self, fn_name, start, end, prototype):
    
    def trim_prototype(prototype):
      proto = prototype[:prototype.rfind('{') - 1]
      return proto[proto.find('^') + 1:]

    self.fn_name = fn_name
    self.start_line = start
    self.end_line = end
    self.prototype = trim_prototype(prototype)

class FileDifferences:
  
  def __init__(self, filename, patch):
    self.filename = filename
    self.file_extension = FileDifferences.get_extension(filename)
    self.current_fn_map = self.get_fn_names(prev=False)
    self.prev_fn_map = self.get_fn_names(prev=True)
    self.fn_to_changed_lines = {}
    self.patch_commit = patch

  @staticmethod
  def get_extension(filename):
    found = filename.rfind('.')
    if found >= 0:
      return filename[found:]
    else:
      return 'none'

  def get_fn_names(self, prev):
    fn_map = {}
    target = os.getcwd() + '/repo/' + self.filename if not prev else os.getcwd() + '/repo_prev/' + self.filename
    proc = subprocess.Popen(['universalctags', '-x', '--c-kinds=fp', '--fields=+ne', '--output-format=json', target], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out, err = proc.communicate()

    if err:
      return fn_map

    fn_table = out.decode('utf-8').strip().split('\n')
    
    #TODO: only looks at function code excluding prototypes - maybe sometime changing prototypes would be useful
    for obj in fn_table:
      if not obj:
        continue
      fn_data = json.loads(obj)
      new_item = FnAttributes(fn_data['name'], fn_data['line'], fn_data['end'] if 'end' in fn_data else fn_data['line'], fn_data['pattern'])
      if fn_data['name'] in fn_map and 'kind' in fn_data and fn_data['kind'] == 'function':
        fn_map[fn_data['name']].append(new_item)
      elif 'kind' in fn_data and fn_data['kind'] == 'function':
        fn_map[fn_data['name']] = [new_item]

    return fn_map

  def match_lines_to_fn(self, new_lines, old_lines):
    success = False

    for fn_name in set(self.current_fn_map.keys()).union(set(self.prev_fn_map.keys())):

      added, removed = [], []

      if fn_name in self.current_fn_map:
        for new_fn_attr in self.current_fn_map[fn_name]:
          for new_line_no in new_lines:
            if new_line_no >= new_fn_attr.start_line and new_line_no <= new_fn_attr.end_line:
              added.append(new_line_no)

      if fn_name in self.prev_fn_map:
        for old_fn_attr in self.prev_fn_map[fn_name]:
          for old_line_no in old_lines:
            if old_line_no >= old_fn_attr.start_line and old_line_no <= old_fn_attr.end_line:
              removed.append(old_line_no)
      
      if fn_name in self.fn_to_changed_lines:
        self.fn_to_changed_lines[fn_name].added_lines.extend(added)
        self.fn_to_changed_lines[fn_name].removed_lines.extend(removed)
        success = True
      elif added or removed:
        self.fn_to_changed_lines[fn_name] = ChangedLinesManager(added, removed, self.patch_commit)
        success = True
      
    return success
        
  # Prints all the data that this object has
  def print(self, pretty):
    fn_list_file = None

    if not pretty:
      OutputManager.print('Updated functions:')
      fn_list_file = open('../updated_functions', 'a')

    for fn_name, lines in self.fn_to_changed_lines.items():
      if pretty and lines:
        print('%s: In function %s' % (colored(self.filename, 'blue'), colored(fn_name, 'green')))
        self.fn_to_changed_lines[fn_name].print_added_lines()
        self.fn_to_changed_lines[fn_name].print_removed_lines()
      elif lines:
        print('%s' % colored(fn_name, 'green'))
        fn_list_file.write('%s\n' % fn_name)

    if not pretty:
      fn_list_file.close()
  
  def print_simple(self):
    for fn_name, lines in self.fn_to_changed_lines.items():
      if lines:
        for line in self.fn_to_changed_lines[fn_name].added_lines:
          print('%s: %s' % (colored(self.filename, 'blue'), line))

class DiffSummary:
  # file_diffs is a list of FileDifferences
  def __init__(self):
    self.file_diffs = []
    self.updated_fn_count = 0

  def add_file_diff(self, file_diff):
    self.file_diffs.append(file_diff)
    self.updated_fn_count += len(file_diff.fn_to_changed_lines)

  def diff_for_json(self):
    file_to_changed_lines = {}
    for file_diff in self.file_diffs:
      for fn_name, lines in file_diff.fn_to_changed_lines.items():
        if lines and lines.added_lines:
          if not file_diff.filename in file_to_changed_lines:
            file_to_changed_lines[file_diff.filename] = file_diff.fn_to_changed_lines[fn_name].added_lines
          else:
            file_to_changed_lines[file_diff.filename].extend(file_diff.fn_to_changed_lines[fn_name].added_lines)

    return file_to_changed_lines

class RepoManager:

  def __init__(self, repo_url, cache, print_mode, save_json, track_json):
    self.repo_url = repo_url
    self.cache = cache
    self.allowed_extensions = ['.c']#, '.h']
    self.print_mode = print_mode
    self.fn_updated_per_commit = {}
    self.other_changed = {}
    self.cloned_repos_paths = []
    self.original_commit = None
    self.save_json = save_json
    self.track_json = track_json

  def get_repo_paths(self):
    # Path where repo is supposed to be
    cwd = os.getcwd()
    return cwd + '/repo', cwd + '/repo_prev'

  # Handles the cloning of a repo
  def clone_repo(self, repo_path, rev=''):
    repo = None

    try:
      repo = pygit2.clone_repository(self.repo_url, repo_path)
    except pygit2.GitError:
      username = input('Enter git username: ')
      password = getpass.getpass('Enter git password: ')
      cred = pygit2.UserPass(username, password)
      try:
        repo = pygit2.clone_repository(self.repo_url, repo_path, callbacks=pygit2.RemoteCallbacks(credentials=cred))
      except ValueError:
        print("Invalid URL!")
        sys.exit(1)
    except Exception as e:
      print(e)
      sys.exit(1)

    return repo

  def get_repo(self, repo_path, rev=''):
    # Keep track of paths of cloned repos
    self.cloned_repos_paths.append(repo_path)

    # Check if we have a repo
    discover_repo_path = pygit2.discover_repository(repo_path, 0, dirname(os.getcwd()))

    repo = None

    # No repo found
    if discover_repo_path is None:
      OutputManager.print("No repo found. Cloning...")
      repo = self.clone_repo(repo_path, rev)
      OutputManager.print("Cloned repo.")
      current_commit = repo.revparse_single('HEAD')
      OutputManager.print('Current commit (patch): ' + current_commit.hex)

      repo = pygit2.Repository(pygit2.discover_repository(repo_path, 0, dirname(os.getcwd())))

      if rev:
        OutputManager.print('Changing to desired commit...')
        try:
          change = repo.revparse_single(rev).hex
        except:
          sys.stdout = OutputManager.old_stdout
          print('Could not parse git revision. Please enter a valid hash (symbols like ^, ~ are permitted)')
          sys.exit(1)
        hash_oid = pygit2.Oid(hex=change)
        repo.reset(hash_oid, pygit2.GIT_RESET_HARD)
        OutputManager.print('Changed to %s.' % (change,))

      return repo

    # if not repo:
    repo = pygit2.Repository(discover_repo_path)

    # A different repo is found
    if repo.remotes['origin'].url != self.repo_url:
      OutputManager.print("Found repo is incorrect. Cloning required repo...")

      # Remove existing contents
      shutil.rmtree(repo_path)

      # Clone
      repo = self.clone_repo(repo_path, rev)

      OutputManager.print("Cloned repo.")
      current_commit = repo.revparse_single('HEAD')
      OutputManager.print('Current commit (patch): ' + current_commit.hex)
    
    else:
      # Found repo is correct, but HEAD may not be pointing to desired commit
      OutputManager.print('Found required repo.')
      OutputManager.print('Current commit (patch): ' + repo.revparse_single('HEAD').hex)
      
      # Check that commits match
      current_commit = repo.revparse_single('HEAD')
      target_commit = None
      try:
        target_commit = repo.revparse_single(rev)
      except:
        sys.stdout = OutputManager.old_stdout
        print('Could not parse git revision. Please enter a valid hash (symbols like ^, ~ are permitted)')
        sys.exit(1)
      
      if target_commit and current_commit.hex != target_commit.hex:
        OutputManager.print('Changing to desired commit...')
        hash_oid = pygit2.Oid(hex=target_commit.hex)
        repo.reset(hash_oid, pygit2.GIT_RESET_HARD)
        OutputManager.print('Changed to %s.' % (target_commit.hex,))
      
    return repo

  def compute_diffs(self, diff, patch_hash=''):
    diff_summary = DiffSummary()
    patches = list(diff.__iter__())

    updated_fn_count = 0
    has_c_files = False
    has_updated_fn = False

    for patch in patches:
      filename = patch.delta.new_file.path

      extension = FileDifferences.get_extension(filename)
      if extension not in self.allowed_extensions:
        if extension not in self.other_changed:
          self.other_changed[extension] = set()
        
        self.other_changed[extension].add(patch_hash)
        continue

      has_c_files = True

      diff_data = FileDifferences(filename, patch_hash)

      for hunk in patch.hunks:
        new_fn_lines = []
        old_fn_lines = []

        for diff_line in hunk.lines:
          if diff_line.content.strip():
            if diff_line.new_lineno > -1:
              new_fn_lines.append(diff_line.new_lineno)
            else:
              old_fn_lines.append(diff_line.old_lineno)

        if diff_data.match_lines_to_fn(new_fn_lines, old_fn_lines):
          has_updated_fn = True

      diff_summary.add_file_diff(diff_data)

    if has_c_files and not has_updated_fn:
      c_ext = '.c'
      if c_ext not in self.other_changed:
       self.other_changed[c_ext] = set()
      self.other_changed[c_ext].add(patch_hash)

    return diff_summary

  def compare_patches_in_range(self, patch_rev, times=1, target_commit=None):
    curr_repo_path, _ = self.get_repo_paths()
    curr_repo = self.get_repo(curr_repo_path, patch_rev)

    distance_to_target = 1
    if target_commit:
      target = curr_repo.revparse_single(target_commit)
      for commit in curr_repo.walk(curr_repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL):
        if commit.hex == target.hex:
          break
        distance_to_target += 1

    if target_commit:
      times = distance_to_target

    for i in range(times):
      head = 'HEAD~'
      prev = curr_repo.revparse_single(head + str(i + 1))
      curr = curr_repo.revparse_single(head + str(i))
      
      OutputManager.print("Comparing with previous commit: " + prev.hex)

      diff = curr_repo.diff(prev, curr, context_lines=0)
      diff_summary = self.compute_diffs(diff, curr.hex)
      OutputManager.print_relevant_diff(diff_summary, self.print_mode)

    # Restore repo to original state
    master = curr_repo.branches['master']
    hash_oid = pygit2.Oid(hex=master.upstream.target.hex)
    curr_repo.reset(hash_oid, pygit2.GIT_RESET_HARD)
    OutputManager.print('Restored to %s' % (curr_repo.revparse_single('HEAD').hex,))

  @staticmethod
  def repo_to_commit(repo, commit_hash):
    repo.reset(pygit2.Oid(hex=commit_hash), pygit2.GIT_RESET_HARD)

  def commit_list(self, repo, start_hash, end_hash=None, times=0):
    commits_range = []

    if end_hash:
      for commit in list(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)):
        if commit.hex == end_hash:
          break
        commits_range.append(commit)
      commits_range.append(repo.revparse_single(end_hash))
      return commits_range

    if times:
      count = 0
      while times > 0:
        commits_range.append(repo.revparse_single(str(start_hash) + "~" + str(count)))
        count += 1
        times -= 1
      return commits_range

  def get_updated_fn_per_commit(self, skip_initial=False, testing=False, end_hash=None, times=0):
    RepoManager.initial_cleanup()

    updates_json = {}

    curr_repo_path, prev_repo_path = self.get_repo_paths()

    patch_repo = self.get_repo(curr_repo_path)
    original_repo = self.get_repo(prev_repo_path)

    empty_tree = None

    commit_count = 0

    if not end_hash and not times:
      commits = list(patch_repo.walk(patch_repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL))
    else:
      commits = self.commit_list(patch_repo, 'HEAD', end_hash, times)

    for commit in commits:
      patch_hash, original_hash = commit.hex, commit.parents[0].hex if commit.parents else None

      commit_count += 1

      if not original_hash:
        empty_tree = original_repo.revparse_single(GIT_EMPTY_TREE_ID)

      RepoManager.repo_to_commit(patch_repo, patch_hash)
      if original_hash:
        RepoManager.repo_to_commit(original_repo, original_hash)

      diff = patch_repo.diff(original_repo.revparse_single('HEAD'), patch_repo.revparse_single('HEAD') if original_hash else empty_tree, context_lines=0)
      diff_summary = self.compute_diffs(diff, patch_hash)

      updated_fn = diff_summary.updated_fn_count

      if self.save_json:
        diffs = diff_summary.diff_for_json()
        if diffs:
          if self.track_json == 'loc':
            lines_no = 0
            for _, lines in diffs.items():
              lines_no += len(lines)
            updates_json[patch_hash] = lines_no
          elif self.track_json == 'diff':
            updates_json[patch_hash] = diffs

      if not original_hash and skip_initial:
        print('Skipping original commit...')
        continue

      if updated_fn in self.fn_updated_per_commit:
        self.fn_updated_per_commit[updated_fn].append(patch_hash)
      else:
        self.fn_updated_per_commit[updated_fn] = [patch_hash]

      if testing:
        print ('Seen %s commits out of %s' % (commit_count, len(commits)))

    if self.save_json:
      with open('output.json', 'w') as fp:
        json.dump(updates_json, fp)

  def order_results(self, other=False):
    target = None
    if other:
      target = self.other_changed.items()
    else:
      target = self.fn_updated_per_commit.items()
      
    ordered = collections.OrderedDict(sorted(target))

    for fn_no, commits in ordered.items():
      ordered[fn_no] = len(commits)

    return ordered

  @staticmethod
  def check_dirs():
    if not os.path.isdir('img'):
      os.mkdir('img')
    if not os.path.isdir('img/skip'):
      os.mkdir('img/skip')

  def plot_fn_per_commit(self, skip):
    ordered_dict = self.order_results()
    plt.figure(1)
    plot = plt.bar(ordered_dict.keys(), ordered_dict.values(), width=0.8, color='g')
    plt.xlabel('Functions changed')
    plt.ylabel('Commits')

    RepoManager.check_dirs()
    path = 'img/skip/' if skip else 'img/'
    plt.savefig(path + 'function_commits.png', bbox_inches='tight')

  def plot_fn_per_commit_restricted(self, skip, limit):
    ordered_dict = self.order_results()
    plt.figure(2)

    if not limit or limit <= 0:
      limit = 25
    elif limit > len(ordered_dict.keys()):
      limit = len(ordered_dict.keys() - 1)

    keys = [k for k in ordered_dict.keys() if k > 0 and k <= limit]
    values = [v for k, v in ordered_dict.items() if k in keys]

    plot = plt.bar(keys, values, width=0.8, color='g')
    plt.xlabel('Functions changed')
    plt.ylabel('Commits')
    
    RepoManager.check_dirs()
    path = 'img/skip/' if skip else 'img/'
    plt.savefig(path + 'function_commits_restricted.png', bbox_inches='tight')

  def plot_other_changed(self, skip):
    ordered_other_dict = self.order_results(other=True)
    plt.figure(3)
    plot = plt.bar(ordered_other_dict.keys(), ordered_other_dict.values(), width=0.8, color='b')
    plt.xticks(rotation='vertical', fontsize=5)
    plt.subplots_adjust(bottom=0.15)
    plt.xlabel('Extensions')
    plt.ylabel('Commits')

    RepoManager.check_dirs()
    path = 'img/skip/' if skip else 'img/'
    plt.savefig(path + 'no_function_commits.png', bbox_inches='tight')    

  def summary(self):
    print('Information from other changed files:')
    print('How many commits changed files of each extension (no functions changed):')
    ordered_other_dict = self.order_results(other=True)
    for ext, commits_no in ordered_other_dict.items():
      if ext != 'none':
        print('%s commits updated %s files' % (commits_no, ext))
      else:
        print('%s commits updated files with no extension (e.g. README, NEWS, etc.)' % (commits_no,))

    print('---------------------------------------------------------------------------------------')

    print('Information from function updates:')
    print('Commits that changed N functions:')
    ordered = self.order_results()
    s = 0
    for fn_no, commits_no in ordered.items():
      s += commits_no
      print('%s %s %s %s functions' % (commits_no, 'commits' if commits_no > 1 else 'commit', 'update' if commits_no > 1 else 'updates' , fn_no))
    print('Commits seen: %s' % (s,))

  @staticmethod
  def initial_cleanup():
    cwd = os.getcwd()
    if (os.path.isdir('repo')):
      shutil.rmtree(cwd + '/repo')
    if (os.path.isdir('repo_prev')):
      shutil.rmtree(cwd + '/repo_prev')

  def cleanup(self):
    if not self.cache:
      for path in self.cloned_repos_paths:
        shutil.rmtree(path)

##### Main program #####
def main(main_args):
  # Initialize argparse
  parser = argparse.ArgumentParser(description='Outputs a list of patched functions and the corresponding source code lines.')

  parser.add_argument('gitrepo', metavar='repo', help='git repo url')
  parser.add_argument('-hash', help='patch hash')
  parser.add_argument('--print-mode', dest='print', choices=['full', 'simple', 'only-fn'], default='full', help='print format')
  parser.add_argument('-c', '--cache', action='store_true', help='do not delete cloned repos after finishing')
  parser.add_argument('--verbose', action='store_true', help='display helpful progress messages')
  parser.add_argument('-s', '--summary', action='store_true', help='prints a summary of the data')
  parser.add_argument('-p', '--plot', action='store_true', help='save graphs of the generated data')
  parser.add_argument('-i', '--skip-initial', dest='skip', action='store_true', help='skip initial commit - can be very large')
  parser.add_argument('-l', '--limit', type=int, help='plot commits up to this one')
  parser.add_argument('-ri', '--rangeInt', type=int, metavar='N', help='look at patches for the previous N commits (preceding HASH)')
  parser.add_argument('-rh', '--range', metavar='INIT_HASH', help='look at patches between INIT_HASH and HASH')
  parser.add_argument('--save-json', dest='json', action='store_true', help='output function update information in JSON format')
  parser.add_argument('--track', dest='track', choices=['loc', 'diff'], default='diff', help='what data to save')

  # Dictionary of arguments
  args_orig = parser.parse_args(main_args)
  args = vars(args_orig)

  # Handle printing
  OutputManager.should_print = bool(args['verbose'])

  repo_manager = RepoManager(args['gitrepo'], bool(args['cache']), args['print'], bool(args['json']), args['track'])

  sys.stdout = OutputManager.output
   
  if args['hash'] and not args['rangeInt'] and not args['range'] :
    repo_manager.compare_patches_in_range(args['hash'], times=1)
  elif args['hash'] and args['range']:
    repo_manager.compare_patches_in_range(args['hash'], target_commit=args['range'])
  elif args['hash'] and args['rangeInt']:
    repo_manager.compare_patches_in_range(args['hash'], times=int(args['rangeInt']))
  elif (args['plot'] or args['summary']) and args['range']:
    repo_manager.get_updated_fn_per_commit(args['skip'], end_hash=args['range'])
  elif (args['plot'] or args['summary']) and args['rangeInt']:
    repo_manager.get_updated_fn_per_commit(args['skip'], times=int(args['rangeInt']))
  elif args['plot'] or args['summary']:
    repo_manager.get_updated_fn_per_commit(args['skip'])

  if args['summary']:
    repo_manager.summary()

  if args['plot']:
    plt.switch_backend('Qt4Agg')
    manager = plt.get_current_fig_manager()
    manager.window.showMaximized()

    repo_manager.plot_fn_per_commit(args['skip'])
    repo_manager.plot_fn_per_commit_restricted(args['skip'], args['limit'])
    repo_manager.plot_other_changed(args['skip'])

  OutputManager.print_all(args['print'] == 'only-fn')
  repo_manager.cleanup()

if __name__ == '__main__':
  main(sys.argv[1:])

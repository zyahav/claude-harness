I want you first to show me the list of tasks. Only every time I will permit you to do one action. Okay, so I don't want you to do everything at once. Please let's do one step at a time.
Show me the list of actions first of all, and then I will tell you if I'm approving the first one.

2:46 PM
Understood. Here's the full list of tasks to upgrade the system:

Task List: Harness-Lab Upgrade
Phase 1: Fix Existing Issues
#	Task	Description
1	Fix imports for --help	Refactor so harness.py --help works without requiring the SDK to be installed
2	Make --spec flag work	Currently parsed but ignored. Make it actually load the specified constitution
3	Fix copy_spec_to_project()	Currently hardcodes app_spec.txt. Should use the spec from --spec flag
4	Define canonical handoff.json schema	Unify the two incompatible formats (initializer vs handoff_to_plan)
5	Add schema validation	Validate handoff.json on load to catch malformed files
6	Update initializer_prompt.md	Make it generate the unified schema format
Phase 2: Implement Lifecycle
#	Task	Description
7	Create lifecycle.py	New module for Git worktree management (create, remove, list)
8	Implement start subcommand	Create branch run/<run-name>, create worktree, record metadata
9	Implement run subcommand	Execute agent in isolated worktree
10	Implement finish subcommand	Verify clean state, push branch, print PR instructions
11	Implement clean subcommand	Remove worktree and local branch after merge
12	Refactor harness.py	Replace current single entry point with subcommand structure
Phase 3: Polish
#	Task	Description
13	Update prompts for worktree	Make prompts aware of the new run structure
14	Update README	Document new CLI and lifecycle
15	Add tests for lifecycle	Test start/run/finish/clean commands
Total: 15 tasks

Do you approve Task 1: Fix imports for --help?

Ok, first action, confirm. 
And test.

2:47 PM
Starting Task 1: Fix imports for --help

The problem is that harness.py imports from agent.py at the top level, and agent.py imports claude_code_sdk which isn't installed. I'll make the imports lazy so --help works without the SDK.


D

read_file


Now I'll move the import inside main() so it only loads when actually running (not during --help):


D

edit_block


Now add the import inside main() just before it's used:


D

edit_block


Now let's test that --help works:


D

execute_command


Task 1 Complete ✅

--help now works without requiring the SDK to be installed.

Ready for Task 2? Make --spec flag work (currently parsed but ignored)

If you test it, you can continue.

2:48 PM
I already tested it - the --help output showed successfully above. Let me also verify it doesn't break when no API key is set:


D

execute_command


Task 1 fully tested ✅ - Both --help and the API key check work without SDK installed.

Moving to Task 2: Make --spec flag work

First, let me see what needs to change. The --spec flag is parsed but needs to be passed through to the agent:


D

read_file


Now let me check prompts.py to see copy_spec_to_project:


D

read_file


Now I understand the chain. I need to:

Pass spec_path from harness.py → run_autonomous_agent() → copy_spec_to_project()
Update copy_spec_to_project() to accept a custom spec path
Let me make these changes:

Step 1: Update prompts.py to accept custom spec path:


D

edit_block


Step 2: Update agent.py to accept and pass spec_path:


D

edit_block


Step 3: Update the copy_spec_to_project call in agent.py:


D

edit_block


Step 4: Update harness.py to pass spec_path to the agent:


1 step
D


edit_block


D


edit_block


Now let's test:

Test 1: --help still works and shows updated description:


D

execute_command


Test 2: Verify copy_spec_to_project function works with custom path:


D

execute_command


Task 2 Complete ✅

The --spec flag now works:

Default still uses prompts/app_spec.txt
Custom spec path is passed through the entire chain
FileNotFoundError raised for missing specs
Help text updated (removed "Parsed but not used yet")
Ready for Task 3? Fix copy_spec_to_project() - Actually this was already done as part of Task 2.

Should I move to Task 4: Define canonical handoff.json schema?

ok

2:51 PM
Starting Task 4: Define canonical handoff.json schema

First, let me review the two existing formats to unify them:

D


read_file


D


read_file


Now I understand the two formats. I'll create a unified schema that takes the best of both:

From handoff_to_plan.md: id, title, acceptance_criteria, meta block (structured)
From initializer_prompt.md: steps (for verification sequence)
Let me create a schema definition file:


D

write_file


The file was written despite the warning. Let me test the schema module:


D

execute_command


Task 4 Complete ✅

Created schema.py with:

Task dataclass with validation
HandoffMeta dataclass for project metadata
Handoff dataclass that holds everything
parse_handoff() - supports both legacy (array) and new (with meta) formats
load_handoff() / save_handoff() - file I/O
validate_handoff_file() - validate from file path
Valid categories defined in VALID_CATEGORIES
The schema is backwards compatible - it can parse the old array format and auto-generate IDs.

Ready for Task 5? Add schema validation (integrate schema.py into the harness)
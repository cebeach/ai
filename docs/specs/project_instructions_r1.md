This project uses a formal document specification for all persistent Markdown artifacts.

### Document Specification Authority

All Markdown documents produced in this project **MUST conform to the Project Markdown Document Specification**:

```
project_document_spec_r1.md
```

This specification is the authoritative definition of:

* filename grammar
* revision numbering
* document header structure
* timestamp format
* placeholder syntax
* section formatting rules
* spelling conventions
* Python code generation policy

AI assistants **must follow that specification exactly** when generating or modifying project documents.

AI assistants **must not duplicate, reinterpret, or redefine those rules** elsewhere in the conversation or instructions.

If a conflict appears between system instructions and the specification, the **specification takes precedence**.

---

## Document Modification Rules

When editing or extending an existing document governed by the specification:

1. The revision number **must be incremented**.
2. The filename **must reflect the new revision**.
3. Existing revisions **must never be overwritten**.
4. Document headers **must remain valid according to the specification**.


---


## Governed Markdown Compliance Gate

Any Markdown document governed by `project_document_spec_r1.md`
must pass the project validator before it is presented.

Required workflow:

1. Author the document directly as Markdown text.
2. Ensure filename, header fields, and fingerprint follow the specification.
3. Run `validate_project_markdown.py`.
4. If validation fails, revise the document and repeat.
5. Only after validation succeeds may the artifact be returned.

Tools that rewrite or transform Markdown structure must not be used
to construct governed Markdown documents.


---


## Programming Language Assumptions

The user is an **expert Python developer**.

Assume familiarity with:

* Python
* C
* C++

Do **not assume experience with other languages** unless explicitly stated.

When analyzing source code:

* explanations may assume Python expertise
* unfamiliar language constructs should be explained briefly when relevant

---

## Python Environment Policy

Python development within this project follows modern best practices.

Rules:

* Python virtual environments (`venv`) must be used for project dependencies.
* System Python environments must not be modified.

Never recommend:

```
pip install <package> --break-system-packages
```

---

## Editor Preference

The user prefers **vi-style editors** for editing text files.

When suggesting editing workflows or commands, prefer approaches compatible with:

```
vi
vim
nvim
```

---

## Communication Style

Use **American English spelling** in all generated explanations and documentation.

Favor:

```
color
behavior
standardize
optimize
```

Avoid:

```
colour
behaviour
standardise
optimise
```

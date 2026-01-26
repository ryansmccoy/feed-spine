"""Generate API reference pages automatically from source code.

This script is run by mkdocs-gen-files during the documentation build.
It scans the source directory and creates markdown files that use
mkdocstrings to render API documentation from docstrings.

See: https://mkdocstrings.github.io/recipes/#automatic-code-reference-pages
"""

from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

# Source directory containing the package
src = Path("src/feedspine")

for path in sorted(src.rglob("*.py")):
    # Skip private modules
    if any(part.startswith("_") and part != "__init__" for part in path.parts):
        continue
    
    # Build the module path (e.g., feedspine.models.record)
    module_path = path.relative_to("src").with_suffix("")
    doc_path = path.relative_to("src").with_suffix(".md")
    full_doc_path = Path("reference", doc_path)
    
    parts = tuple(module_path.parts)
    
    # Handle __init__.py files
    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")
    
    # Skip if no parts (shouldn't happen, but safety check)
    if not parts:
        continue
    
    # Add to navigation
    nav[parts] = doc_path.as_posix()
    
    # Generate the markdown file that mkdocstrings will process
    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        identifier = ".".join(parts)
        fd.write(f"# {parts[-1]}\n\n")
        fd.write(f"::: {identifier}\n")
    
    # Set edit path for GitHub edit links
    mkdocs_gen_files.set_edit_path(full_doc_path, path.relative_to("src"))

# Generate the navigation file for literate-nav
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())

import json
import argparse
import os
import sys

from .utils import parse_doc
from .utils import get_lfs_version
from .utils import get_packages
from .utils import check_md5sums
from .utils import get_sections
from .utils import add_package_commands
from .utils import write_section_cmds
from .classes import HTMLParseError

from .__init__ import __version__

def main():
    """Generate LFS build scripts."""

    ap = argparse.ArgumentParser(
        description="Generate LFS build scripts."
    )
    ap.version = __version__
    ap.add_argument('--timezone',
                    action='store',
                    dest='timezone',
                    default='Europe/Berlin',
                    help="Timezone string")
    ap.add_argument('--papersize',
                    action='store',
                    dest='papersize',
                    default='A4',
                    help="Papersize string")
    ap.add_argument('--newline',
                    action='store',
                    dest='newline', default='LF',
                    choices=['LF', 'CRLF'],
                    help="End-of-line specifier")
    ap.add_argument('--dbdir',
                    action='store',
                    dest='db_dir', default='.',
                    help="Directory to look for the build database")
    ap.add_argument('--sourcedir',
                    action='store',
                    dest='source_dir', default='.',
                    help="Directory with the package sources")
    ap.add_argument('--outdir',
                    action='store',
                    dest='out_dir', default='.',
                    help="Directory where scripts are written to")
    ap.add_argument('--htmldir',
                    action='store',
                    dest='html_dir', default='.',
                    help="Directory to look for LFS html files")
    ap.add_argument('--version',
                    action='version')
    args = ap.parse_args()

    # set up build db
    db_file = os.path.join(args.db_dir, 'build_db.json')
    try:
        with open(db_file, 'r') as f:
            build_db = json.load(f)
    except FileNotFoundError as e:
        print(e)
        sys.exit()

    build_db['timezone'] = args.timezone
    build_db['papersize'] = args.papersize

    # find and parse LFS html file
    try:
        doc = parse_doc(args.html_dir)
    except FileNotFoundError as e:
        print(e)
        sys.exit()
    
    try:
        lfs_version = get_lfs_version(doc)
    except HTMLParseError as e:
        print(e)
        sys.exit()
    print(f"Using LFS version {lfs_version} html file...")
    if "lfs_version" in build_db:
        if lfs_version != build_db["lfs_version"]:
            print("ERROR: LFS html version does not match build_db version")
            sys.exit()
    else:
        print("WARNING: Version missing in build_db. Make sure it matches LFS html version")
    # get package data and check md5 sums
    try:
        packages = get_packages(doc)
    except HTMLParseError as e:
        print(e)
        sys.exit()
    source_dir = os.path.join(args.source_dir, "sources")
    status = check_md5sums(source_dir, packages)
    if status:
        print("Package MD5 checksums ok")
    else:
        print("WARNING: At least one MD5 check failed")

    # get section commands
    # tools sections
    print("Generating LFS build scripts...")
    sections_tools1 = get_sections(doc, build_db, "tool1")
    sections_tools1 = add_package_commands(sections_tools1, packages, build_db)

    sections_tools2 = get_sections(doc, build_db, "tool2")
    sections_tools2 = add_package_commands(sections_tools2, packages, build_db)

    # system sections
    sections_system = get_sections(doc, build_db, "system")
    sections_system = add_package_commands(sections_system, packages, build_db)
    
    # merge all section and write scripts to file
    all_sections = sections_tools1 + sections_tools2 + sections_system
    write_section_cmds(all_sections, args, lfs_version)

    for sec in all_sections:
        if not sec.output:
            print(f"WARNING: no output for {sec.chapter_id}")

    print("Done.")
    sys.exit(0)

if __name__ == '__main__':
    main()
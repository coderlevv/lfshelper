"""Utility functions to generate LFS build scripts.

"""

import os
from os.path import basename, join, exists
from os import listdir
import hashlib
import re
import sys
import io
import json
import argparse
from lxml import etree
from .classes import Section, Package, HTMLParseError
from .__init__ import __version__
from datetime import datetime

def get_license_string(lfs_version, instructions=True):
    license_string =  """
# Script generated with lfshelper package version {}, {}.
# The lfshelper package is licensed under the MIT license.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
""".format(__version__, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    if instructions:
        license_string += """
#
# Computer instructions in this script were extracted and adapted from the LFS book
# (version {}), Copyright (c) Gerard Beekmans.
""".format(lfs_version)
    return license_string

def parse_doc(html_dir):
    """Find LFS html file and parse it."""

    files = listdir(html_dir)
    html_file_match = [f for f in files if re.findall("LFS-BOOK.*-NOCHUNKS.html", f)]
    if len(html_file_match) == 0:
        print("No LFS-BOOK html file found.")
        sys.exit()
    elif len(html_file_match) > 1:
        print("Found multiple LFS-BOOK html files. using first entry...")
    lfs_html_file = join(html_dir, html_file_match[0])
    parser = etree.HTMLParser()
    doc = etree.parse(lfs_html_file, parser=parser)
    return doc


def get_lfs_version(doc):
    """Extract LFS version from html document."""

    qry = doc.xpath("//body")
    if not qry:
        raise HTMLParseError("Couldn't parse LFS version from html file")
    body = qry[0]
    if not 'id' in body.attrib:
        raise HTMLParseError("Couldn't parse LFS version from html file")
    id_split = body.attrib['id'].split('-')
    if len(id_split) < 2:
        raise HTMLParseError("Couldn't parse LFS version from html file")
    lfs_version = id_split[1]
    if not re.match(r"\d+\.\d+",lfs_version):
        raise HTMLParseError("Couldn't parse LFS version from html file")
    return lfs_version


def get_md5_hash(source_dir, chunksize=8192):
    """Generate MD5 hash of package file."""

    with open(source_dir, "rb") as f:
        file_hash = hashlib.md5()
        chunk = f.read(chunksize)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(chunksize)
    return file_hash.hexdigest()


def get_sections(doc, build_db, part):
    """Extract section data from LFS html document."""

    res = []
    h2_list = doc.xpath("//h2[@class='title']")
    for h2 in h2_list:
        a = h2.xpath(f"a[starts-with(@id, 'ch-')]")
        if len(a) == 1:
            chapter_id = a[0].attrib['id']
            if not chapter_id in build_db:
                #print(f"WARNING: section {chapter_id} not found in build_db!")
                continue
            entry = build_db[chapter_id]
            if not part in entry['part']:
                continue
            txt = h2.xpath("text()")[1]
            m = re.search(r"(\d+)\.(\d+)\.", txt)
            title_div = h2.getparent().getparent().getparent()
            chapter = int(m[1])
            section = int(m[2])
            section = Section(chapter, section, chapter_id, title_div)
            res.append(section)
    return res


def get_packages(doc):
    """Extract package data from LFS html document."""

    qry = doc.xpath("//p[contains(text(), 'Download or otherwise obtain the following packages:')]")[0].getnext()
    if len(qry) == 0:
        raise HTMLParseError("Couldn't parse package data from html file.")
    dl_div = qry[0] 
    #if dl_div is None:
    #    raise HTMLParseError("Couldn't parse package data from html file.")
    dl = dl_div.xpath(".//dd/p[contains(text(), 'Download')]")
    package_list = [basename(d.getchildren()[0].attrib['href']) for d in dl]
    md5 = dl_div.xpath(".//dd/p[contains(text(), 'MD5')]")
    md5_list = [m.getchildren()[0].text.strip() for m in md5]
    if len(package_list) != len(md5):
        raise HTMLParseError("Couldn't parse package data from html file.")
    res = [Package(pack, md5) for pack, md5 in zip(package_list, md5_list)]
    return res


def check_md5sums(source_dir, packages, verbose=False):
    """Compare generated MD5 with MD5 from html document."""

    overall_status = True
    for p in packages:
        f = join(source_dir, p.name)
        if not exists(f):
            if verbose:
                print(f"WARNING: package {p.name} not found!")
            continue
        if verbose:
            print(f"Found package {p.name}")
        md5 = get_md5_hash(f)
        if md5 == p.md5:
            check_status = "ok"
        else:
            check_status = "failed"
            overall_status = False
        if verbose: print(f"Checking md5 sum of package {p.name}: {check_status}")
    return overall_status


def add_package_commands(sections, packages, build_db):
    """Extract commands from the sections in the LFS book."""

    for sec in sections:
        if not sec.chapter_id in build_db:
            print(f"WARNING: no {sec.chapter_id} entry in build database.")
            continue
        base = build_db[sec.chapter_id]['package_base']
        if base != "":
            if 'changedir' in build_db[sec.chapter_id]:
                sec.changedir = build_db[sec.chapter_id]['changedir']

            if 'newfile' in build_db[sec.chapter_id]:
                sec.newfile = build_db[sec.chapter_id]['newfile']
            
            if 'append' in build_db[sec.chapter_id]:
                sec.append = build_db[sec.chapter_id]['append']
            
            if 'message' in build_db[sec.chapter_id]:
                sec.message = build_db[sec.chapter_id]['message']

            if base in ["nonpackage"]:
                sec.package = base
            else:
                found_package = None
                for p in packages:
                    if p.base == base:
                        found_package = p
                        break
                sec.package = found_package
                #TODO: raise an exception

            if 'package' in build_db[sec.chapter_id]:
                sec.package = Package(build_db[sec.chapter_id]['package'], "")

            cmd_str = ""
            cmds = sec.title_div.getnext().xpath(".//kbd[@class='command']")
            for cmd in cmds:
                subcmd = ''.join(cmd.itertext())
                cmd_str += subcmd + '\n'

            if 'replace' in build_db[sec.chapter_id]:
                replace_cmds = build_db[sec.chapter_id]['replace']
                values = []
                for idx in range(len(replace_cmds)):
                    entry = replace_cmds[str(idx)]
                    pat = entry[0]
                    rep = entry[1]
                    if len(entry) > 2:
                        key = entry[2]
                        values.append(build_db[key])
                    cmd_str = cmd_str.replace(pat, rep)
                if len(values) > 0:
                    cmd_str = cmd_str % tuple(values)
            
            with io.StringIO(cmd_str) as s:
                cmd_str = ""
                line = s.readline()
                while line:
                    if re.search('make.+(check|test)\\s+', line):
                        line = line.strip() + ' || true\n'
                    cmd_str += line
                    line = s.readline()
            
            sec.cmds = cmd_str

    return sections
            

def split_cmds(sec):
    """Splits a command string at logout and bash shell calls."""
    
    cmd_array = []
    cmd_str = ""
    for c in sec.cmds.split('\n'):
        cmd_str += c + '\n'
        if re.search(r".+bash\s+--login", c) or \
            re.search(r"\blogout\b", c):
            cmd_array.append(cmd_str)
            cmd_str = ""
    if cmd_str.strip() != "":
        cmd_array.append(cmd_str)
    return cmd_array


def write_section_cmds(sections, args, lfs_version):
    """Write section commands to file."""

    if args.newline == 'LF':
        newline = '\n'
    else:
        newline = '\r\n'
    part_count = 1
    fname = join(args.out_dir, f"lfs_build_part{part_count}.sh")
    fout = open(fname, "w", newline=newline)
    #shell_str = "#!/bin/bash"
    # shell_str = ""
    # print(shell_str, file=fout)
    print(get_license_string(lfs_version), file=fout)

    for sec in sections:
        cmd_array = split_cmds(sec)
        for c in cmd_array:
            if sec.newfile:
                fout.close()
                part_count += 1
                fname = join(args.out_dir, f"lfs_build_part{part_count}.sh")
                fout = open(fname, "w", newline=newline)
                #print(shell_str, file=fout)
                print(get_license_string(lfs_version), file=fout)
        
            if sec.package:
                print(f"### {sec.chapter_id}", file=fout)
                if sec.package not in ["nonpackage"]:
                    print(f"tar {sec.package.tar} {sec.package.name}", file=fout)
                    print(f"cd {sec.package.unpack_name}", file=fout)
                
                print(c, file=fout)
                sec.output = True
                
                if sec.package not in ["nonpackage"]:
                    cd_str = "cd .."
                    if sec.changedir:
                        for _ in range(sec.changedir):
                            cd_str += "/.."
                    print(cd_str, file=fout)
                    print(f"rm -rf {sec.package.unpack_name}", file=fout)

            if re.search(r".+bash\s+--login", c) or re.search(r"\blogout\b", c):
                fout.close()
                part_count += 1
                fname = join(args.out_dir, f"lfs_build_part{part_count}.sh")
                fout = open(fname, "w", newline=newline)
                #print(shell_str, file=fout)
                print(get_license_string(lfs_version), file=fout)
        
        if sec.append:
            for c in sec.append:
                print(c, file=fout)

        if sec.message:
            for m in sec.message:
                print(f"echo '{m}'", file=fout)

    fout.close()


def write_config_script(build_db, args, lfs_version):
    """Copy LFS config files."""

    if args.newline == 'LF':
        newline = '\n'
    else:
        newline = '\r\n'
    fname = join(args.out_dir, "lfs_build_config.sh")
    fout = open(fname, "w", newline=newline)
    print(get_license_string(lfs_version, instructions=False), file=fout)
    
    lfs_config = build_db.get("config")
    cwd = os.getcwd()
    try:
        config_files = os.listdir(os.path.join(cwd, "config"))
    except:
        config_files = []

    if "copy" in lfs_config:
        for src, tgt in lfs_config["copy"]:
            if src in config_files:
                cmd = f"cp -v config/{src} {os.path.join(tgt, src)}"
                print(cmd, file=fout)

    fout.close()


if __name__ == '__main__':
    pass

#!/usr/bin/env python
# This module along with accompanying bcp47.json, tries to parse BCP47 like language IDs
# This is not 100% compatible with BCP47
# We diverge on :
#   using three letter code for all languages
#      => language: 3 letter (lowercase), script: 4 letter (title case), and country: 2 letter (uppercase)
#   no support for too many variations: limited to (lll, Ssss, CC) i.e (lang, script, country)
#
# Author: Thamme Gowda [tg (at) isi.edu]
# Created: 10/3/21

import json
from collections import namedtuple
from pathlib import Path
from typing import Optional, Union

from mtdata.iso import iso3_code


def load_json(path: Path):
    assert path.exists()
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


class BCP47Tag(namedtuple('BCP47Tag', ('lang', 'script', 'region', 'tag'))):
    __slots__ = ()
    joiner = '_'  # per BCP47, we must use '-' hyphen not underscore, but we use '-' to separate languages e.g. eng-deu

    def __new__(cls, lang, script: Optional[str] = None, region: Optional[str] = None, tag: Optional[str] = None):
        tag = tag or ''.join([lang,
                              f'{cls.joiner}{script}' if script else '',
                              f'{cls.joiner}{region}' if region else ''])
        obj = super(BCP47Tag, cls).__new__(cls, lang, script, region, tag)
        # obj.tag = tag
        return obj

    def __str__(self):
        return self.tag

    def __repr__(self):
        return f'BCP47({self.tag})'

    def __lt__(self, other):
        return self.tag > other.tag

    def is_compatible(self, lang2: Union[str, 'BCP47Tag']):

        if isinstance(lang2, str):
            lang2 = bcp47(lang2)
        # exact same tag => true
        if self.tag == lang2.tag:
            return True
        # languages or scripts are different
        if self.lang != lang2.lang or self.script != lang2.script:
            return False
        # one of them is general, other is a variant of region
        # e.g. eng vs eng_US
        if not self.region or not lang2.region:
            return True
        return False


class BCP47Parser:

    def __init__(self, data):
        self.data = data
        assert all(key in data for key in ['languages', 'scripts', 'countries']), 'malformed bcp4j data'
        self.scripts = {code: name for code, name in data['scripts']}
        self.countries = {code: name for code, name in data['countries']}
        self.languages = {code3: (code2, name) for code3, code2, name in data['languages']}
        for key in self.languages:  # validation
            assert key == iso3_code(key, fail_error=True)
        self.default_scripts = {}  # these needs suppression; eng-Latn is just eng, as Latn is default
        for lang_code, script_code, lang_name in data['default_scripts']:
            code3 = iso3_code(lang_code, fail_error=True)
            assert script_code in self.scripts
            self.default_scripts[code3] = script_code

    def parse(self, tag) -> BCP47Tag:
        """
        Parameters
        ----------
        tag : tag to be parsed

        Returns
        -------
            BCP47Tag
        """
        code_orig = tag
        tag = tag.replace('_', '-').strip()
        assert tag
        parts = tag.split('-')
        assert 1 <= len(parts) <= 3, f'BCP47 code longer than 3 parts not supported yet; given {code_orig}'
        lang, script, region = None, None, None
        # part 1: it has to be language
        lang = iso3_code(parts[0], default=None)
        if not lang or lang not in self.languages:
            raise ValueError(f'Unable to recognize {code_orig}; Unknown language')
        # assert lang in self.languages, f'Language "{lang}" is invalid; input: {code_orig}'

        parts = parts[1:]
        if parts:  # part 2 can be either script or region code
            if parts[0].title() in self.scripts:
                script = parts[0].title()
            elif parts[0].upper() in self.countries:
                region = parts[0].upper()
            elif parts[0] == 'XX':      # placeholder for a country
                pass
            else:
                raise ValueError(f'Unable to parse {code_orig}')
            parts = parts[1:]
        if parts:  # part 3, if it exists, must be a region
            assert script
            assert not region
            if parts[0].upper() in self.countries:
                region = parts[0].upper()
            else:
                raise ValueError(f"Cant find {code_orig}; Unknown region")
            parts = parts[1:]
        assert not parts  # all parts are consumed
        if script and lang in self.default_scripts and self.default_scripts[lang] == script:
            script = None  # suppress script
        return BCP47Tag(lang=lang, script=script, region=region)

    def try_parse(self, tag, default=None):
        """
        Tries to parse a language tag; upon failure, returns the default value
        Parameters
        ----------
        tag : tag to be parsed
        default : default value to return upon failure

        Returns
        -------
        """
        try:
            return self(tag)
        except ValueError:
            return default

    def __call__(self, tag) -> BCP47Tag:
        """
        Parameters
        ----------
        tag : tag to be parsed
        Returns
        -------
           BCP47Tag
        """
        if isinstance(tag, BCP47Tag):
            return tag
        return self.parse(tag)


data_file = Path(__file__).parent / "bcp47.json"
bcp47_data = load_json(data_file)
bcp47 = BCP47Parser(data=bcp47_data)

if __name__ == '__main__':
    import argparse

    p = argparse.ArgumentParser(prog='python -m mtdata.iso.bcp47', description="BCP47 lookup tool")
    p.add_argument("langs", nargs='+', help="Language code or name that needs to be looked up. "
                                            "When no language code is given, all languages are listed.")
    args = vars(p.parse_args())
    if args.get('langs'):
        print("INPUT\tSTD\tLANG\tSCRIPT\tREGION")
        for inp in args['langs']:
            tag = bcp47(inp)
            print(f'{inp}\t{tag}\t{tag.lang}\t{tag.script}\t{tag.region}')

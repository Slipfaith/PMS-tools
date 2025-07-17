# sdlxliff_split_merge/xml_utils.py

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransUnit:
   id: str
   full_xml: str
   start_pos: int
   end_pos: int
   group_id: Optional[str] = None
   source_text: str = ""
   target_text: str = ""
   approved: bool = False
   translated: bool = False

   def is_translated(self) -> bool:
       return bool(self.target_text.strip()) or self.translated


class XmlStructure:

   def __init__(self, xml_content: str):
       self.xml_content = xml_content
       self.trans_units: List[TransUnit] = []
       self.groups: Dict[str, List[int]] = {}
       self.header_end_pos = 0
       self.footer_start_pos = 0
       self.encoding = "utf-8"

       self._parse_structure()

   def _parse_structure(self):
       encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', self.xml_content)
       if encoding_match:
           self.encoding = encoding_match.group(1)

       body_match = re.search(r'<body[^>]*>', self.xml_content)
       if body_match:
           self.header_end_pos = body_match.end()

       body_close_match = re.search(r'</body>', self.xml_content)
       if body_close_match:
           self.footer_start_pos = body_close_match.start()

       self._parse_trans_units()
       self._parse_groups()

   def _parse_trans_units(self):
       pattern = re.compile(
           r'<trans-unit\s+[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</trans-unit>',
           re.DOTALL
       )

       for match in pattern.finditer(self.xml_content):
           trans_unit_id = match.group(1)
           full_xml = match.group(0)

           source_text = self._extract_segment_text(full_xml, 'source')
           target_text = self._extract_segment_text(full_xml, 'target')

           approved = 'approved="yes"' in full_xml
           translated = bool(target_text.strip())

           trans_unit = TransUnit(
               id=trans_unit_id,
               full_xml=full_xml,
               start_pos=match.start(),
               end_pos=match.end(),
               source_text=source_text,
               target_text=target_text,
               approved=approved,
               translated=translated
           )

           self.trans_units.append(trans_unit)

   def _extract_segment_text(self, xml: str, segment_type: str) -> str:
       pattern = f'<{segment_type}[^>]*>(.*?)</{segment_type}>'
       match = re.search(pattern, xml, re.DOTALL)

       if not match:
           return ""

       content = match.group(1)
       content = re.sub(r'<\?xml[^>]*\?>', '', content)
       content = content.strip()

       display_text = re.sub(r'<(?!/?[gx]|/?mrk|/?bpt|/?ept|/?ph|/?it)[^>]+>', '', content)
       return display_text.strip()

   def _parse_groups(self):
       group_pattern = re.compile(r'<group[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</group>', re.DOTALL)

       for group_match in group_pattern.finditer(self.xml_content):
           group_id = group_match.group(1)

           group_trans_units = []
           for i, trans_unit in enumerate(self.trans_units):
               if group_match.start() <= trans_unit.start_pos <= group_match.end():
                   trans_unit.group_id = group_id
                   group_trans_units.append(i)

           self.groups[group_id] = group_trans_units

   def get_header(self) -> str:
       return self.xml_content[:self.header_end_pos]

   def get_complete_header(self) -> str:
       return self.xml_content[:self.header_end_pos]

   def get_footer(self) -> str:
       return self.xml_content[self.footer_start_pos:]

   def get_body_content_with_structure(self, start_idx: int, end_idx: int) -> str:
       if not self.trans_units or start_idx >= len(self.trans_units):
           return ""

       end_idx = min(end_idx, len(self.trans_units))
       start_pos, end_pos = self._find_structure_boundaries(start_idx, end_idx)
       content = self.xml_content[start_pos:end_pos]
       return content

   def _find_structure_boundaries(self, start_idx: int, end_idx: int) -> Tuple[int, int]:
       if not self.trans_units:
           return 0, 0

       start_unit = self.trans_units[start_idx]
       start_pos = start_unit.start_pos

       if start_unit.group_id:
           group_pattern = f'<group[^>]*id=["\']' + re.escape(start_unit.group_id) + '["\'][^>]*>'
           group_match = re.search(group_pattern, self.xml_content)
           if group_match and group_match.start() < start_pos:
               start_pos = group_match.start()

       end_unit = self.trans_units[end_idx - 1]
       end_pos = end_unit.end_pos

       if end_unit.group_id:
           group_start_pattern = f'<group[^>]*id=["\']' + re.escape(end_unit.group_id) + '["\'][^>]*>'
           group_start = re.search(group_start_pattern, self.xml_content)
           if group_start:
               group_content = self.xml_content[group_start.start():]
               group_end_match = re.search(r'</group>', group_content)
               if group_end_match:
                   group_end_pos = group_start.start() + group_end_match.end()
                   if group_end_pos > end_pos:
                       end_pos = group_end_pos

       return start_pos, end_pos

   def get_body_content(self, start_idx: int, end_idx: int) -> str:
       return self.get_body_content_with_structure(start_idx, end_idx)

   def get_segments_count(self) -> int:
       return len(self.trans_units)

   def get_translated_count(self) -> int:
       return sum(1 for unit in self.trans_units if unit.is_translated())

   def get_word_count(self) -> int:
       total_words = 0
       for unit in self.trans_units:
           words = len(unit.source_text.split())
           total_words += words
       return total_words

   def validate_structure_integrity(self) -> Dict[str, any]:
       issues = []

       for group_id, unit_indices in self.groups.items():
           if not unit_indices:
               issues.append(f"Пустая группа: {group_id}")
               continue

           for idx in unit_indices:
               if idx >= len(self.trans_units):
                   issues.append(f"Неверный индекс в группе {group_id}: {idx}")

       return {
           'valid': len(issues) == 0,
           'issues': issues,
           'groups_count': len(self.groups),
           'total_segments': len(self.trans_units),
           'encoding': self.encoding
       }


class TransUnitParser:

   @staticmethod
   def parse_trans_unit(xml_content: str) -> Optional[TransUnit]:
       pattern = re.compile(
           r'<trans-unit\s+[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</trans-unit>',
           re.DOTALL
       )

       match = pattern.search(xml_content)
       if not match:
           return None

       trans_unit_id = match.group(1)
       full_xml = match.group(0)

       source_text = TransUnitParser._extract_segment_text(full_xml, 'source')
       target_text = TransUnitParser._extract_segment_text(full_xml, 'target')

       approved = 'approved="yes"' in full_xml
       translated = bool(target_text.strip())

       return TransUnit(
           id=trans_unit_id,
           full_xml=full_xml,
           start_pos=match.start(),
           end_pos=match.end(),
           source_text=source_text,
           target_text=target_text,
           approved=approved,
           translated=translated
       )

   @staticmethod
   def _extract_segment_text(xml: str, segment_type: str) -> str:
       pattern = f'<{segment_type}[^>]*>(.*?)</{segment_type}>'
       match = re.search(pattern, xml, re.DOTALL)

       if not match:
           return ""

       content = match.group(1)
       content = re.sub(r'<\?xml[^>]*\?>', '', content)
       text = re.sub(r'<(?!/?[gx]|/?mrk|/?bpt|/?ept|/?ph|/?it)[^>]+>', '', content)
       return text.strip()

   @staticmethod
   def update_trans_unit_target(xml_content: str, new_target: str) -> str:
       target_pattern = r'<target[^>]*>.*?</target>'

       if re.search(target_pattern, xml_content, re.DOTALL):
           return re.sub(target_pattern, f'<target>{new_target}</target>', xml_content, flags=re.DOTALL)

       source_pattern = r'(<source[^>]*>.*?</source>)'
       replacement = r'\1\n      <target>' + new_target + '</target>'

       return re.sub(source_pattern, replacement, xml_content, flags=re.DOTALL)

   @staticmethod
   def mark_as_translated(xml_content: str) -> str:
       xml_content = re.sub(r'approved="[^"]*"', 'approved="yes"', xml_content)

       if 'approved=' not in xml_content:
           xml_content = xml_content.replace('<trans-unit ', '<trans-unit approved="yes" ')

       return xml_content


def extract_all_sdl_elements(xml_content: str) -> Dict[str, str]:
   sdl_elements = {}

   ref_files_pattern = r'<sdl:ref-files[^>]*>.*?</sdl:ref-files>'
   ref_files_match = re.search(ref_files_pattern, xml_content, re.DOTALL)
   if ref_files_match:
       sdl_elements['ref_files'] = ref_files_match.group(0)

   sdl_cxts_pattern = r'<sdl:cxts[^>]*>.*?</sdl:cxts>'
   sdl_cxts_matches = re.findall(sdl_cxts_pattern, xml_content, re.DOTALL)
   if sdl_cxts_matches:
       sdl_elements['contexts'] = '\n'.join(sdl_cxts_matches)

   file_info_pattern = r'<file-info[^>]*>.*?</file-info>'
   file_info_match = re.search(file_info_pattern, xml_content, re.DOTALL)
   if file_info_match:
       sdl_elements['file_info'] = file_info_match.group(0)

   return sdl_elements


def restore_sdl_elements(xml_content: str, sdl_elements: Dict[str, str]) -> str:
   restored_content = xml_content

   if 'ref_files' in sdl_elements and '<sdl:ref-files' not in restored_content:
       header_end = restored_content.find('</header>')
       if header_end > 0:
           ref_files = sdl_elements['ref_files']
           restored_content = (restored_content[:header_end] +
                               '\n' + ref_files + '\n' +
                               restored_content[header_end:])

   return restored_content


def find_trans_units_and_groups(xml_bytes: bytes) -> Dict[str, Any]:
   try:
       xml_str = xml_bytes.decode('utf-8')
   except UnicodeDecodeError:
       xml_str = xml_bytes.decode('utf-16', errors='replace')

   structure = XmlStructure(xml_str)

   trans_units = []
   for i, unit in enumerate(structure.trans_units):
       class MockMatch:
           def __init__(self, start, end):
               self._start = start
               self._end = end

           def start(self):
               return self._start

           def end(self):
               return self._end

       trans_units.append({
           'match': MockMatch(unit.start_pos, unit.end_pos),
           'id': unit.id,
           'group_id': structure.groups.get(unit.group_id, []).index(i) if unit.group_id else None
       })

   groups = []
   for group_id, unit_indices in structure.groups.items():
       if unit_indices:
           start_pos = min(structure.trans_units[i].start_pos for i in unit_indices)
           end_pos = max(structure.trans_units[i].end_pos for i in unit_indices)

           class MockMatch:
               def __init__(self, start, end):
                   self._start = start
                   self._end = end

               def start(self):
                   return self._start

               def end(self):
                   return self._end

           groups.append({
               'match': MockMatch(start_pos, end_pos),
               'trans_unit_indices': unit_indices
           })

   return {
       'trans_units': trans_units,
       'groups': groups
   }


def extract_source_word_count(trans_unit_bytes: bytes) -> int:
   try:
       trans_unit_str = trans_unit_bytes.decode('utf-8')
   except UnicodeDecodeError:
       trans_unit_str = trans_unit_bytes.decode('utf-16', errors='replace')

   unit = TransUnitParser.parse_trans_unit(trans_unit_str)
   if unit:
       return len(unit.source_text.split())
   return 0


def validate_sdlxliff_structure(xml_bytes: bytes) -> Tuple[bool, Optional[str]]:
   try:
       xml_str = xml_bytes.decode('utf-8')
   except UnicodeDecodeError:
       try:
           xml_str = xml_bytes.decode('utf-16')
       except UnicodeDecodeError:
           return False, "Encoding error"

   from .validator import SdlxliffValidator
   validator = SdlxliffValidator()
   return validator.validate(xml_str)


def get_header_footer(xml_bytes: bytes, units_list: List[dict]) -> Tuple[bytes, bytes]:
   try:
       xml_str = xml_bytes.decode('utf-8')
   except UnicodeDecodeError:
       xml_str = xml_bytes.decode('utf-16', errors='replace')

   structure = XmlStructure(xml_str)

   header = structure.get_complete_header().encode(structure.encoding)
   footer = structure.get_footer().encode(structure.encoding)

   return header, footer


def extract_metadata_from_header(header_str: str) -> Dict[str, str]:
   metadata = {}

   file_match = re.search(r'<file([^>]+)>', header_str)
   if file_match:
       attrs_str = file_match.group(1)

       attr_pattern = re.compile(r'(\w+)="([^"]+)"')
       for match in attr_pattern.finditer(attrs_str):
           metadata[match.group(1)] = match.group(2)

   file_info_match = re.search(
       r'<file-info[^>]*>(.*?)</file-info>',
       header_str,
       re.DOTALL
   )

   if file_info_match:
       file_info_content = file_info_match.group(1)

       value_pattern = re.compile(r'<value key="([^"]+)">([^<]+)</value>')
       for match in value_pattern.finditer(file_info_content):
           metadata[f'file-info:{match.group(1)}'] = match.group(2)

   ref_files_match = re.search(r'<sdl:ref-files[^>]*>', header_str)
   if ref_files_match:
       metadata['sdl:ref-files'] = 'present'

   sdl_cxts_count = len(re.findall(r'<sdl:cxts[^>]*>', header_str))
   if sdl_cxts_count > 0:
       metadata['sdl:cxts_count'] = str(sdl_cxts_count)

   return metadata
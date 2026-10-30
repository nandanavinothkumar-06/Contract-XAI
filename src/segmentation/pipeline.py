import hashlib
from typing import List, Optional
from src.preprocessing.schema import PreprocessedRecord
from .schema import SegmentedDocument, Segment, SegmentType, EvidenceAssociation
from .config import SegmentationConfig
from .scanner import split_into_blocks
from .numbering import detect_numbering
from .headings import is_likely_heading
from .definitions import is_definition
from .hierarchy import build_hierarchy
from .validation import validate_segments

class SegmentationPipeline:
    def __init__(self, config: SegmentationConfig = None):
        self.config = config or SegmentationConfig()
        self.version = "1.0.1"
        
    def _generate_segment_id(self, doc_id: str, start: int, end: int) -> str:
        s = f"{doc_id}_{start}_{end}_{self.version}"
        return hashlib.sha256(s.encode()).hexdigest()[:16]

    def _map_processed_offset(self, original_start: int, original_end: int, record: PreprocessedRecord):
        if len(record.processed_text) == len(record.original_record.text):
            return original_start, original_end
        return None, None

    def _assemble_segments(self, blocks: List[tuple], text: str) -> List[dict]:
        segments = []
        current_seg = None
        for block_text, start, end in blocks:
            num, _ = detect_numbering(block_text)
            is_hdg = is_likely_heading(block_text, bool(num))
            is_def = is_definition(block_text)
            
            is_new = bool(num) or is_hdg or is_def
            
            if current_seg is None:
                current_seg = {"start": start, "end": end, "num": num, "hdg": is_hdg, "def": is_def}
            elif is_new or not current_seg.get("num"):
                segments.append(current_seg)
                current_seg = {"start": start, "end": end, "num": num, "hdg": is_hdg, "def": is_def}
            else:
                current_seg["end"] = end
                
        if current_seg:
            segments.append(current_seg)
            
        return segments

    def segment_record(self, record: PreprocessedRecord) -> SegmentedDocument:
        source_dataset = record.original_record.source_dataset
        doc_id = record.original_record.record_id 
        full_text = record.original_record.text
        
        blocks = split_into_blocks(full_text)
        assembled = self._assemble_segments(blocks, full_text)
        
        segments = []
        for i, seg_dict in enumerate(assembled):
            start = seg_dict["start"]
            end = seg_dict["end"]
            num = seg_dict["num"]
            is_hdg = seg_dict["hdg"]
            is_def = seg_dict["def"]
            
            p_start, p_end = self._map_processed_offset(start, end, record)
            
            seg_type = SegmentType.PARAGRAPH
            if is_hdg:
                seg_type = SegmentType.DOCUMENT_TITLE if i == 0 else SegmentType.SECTION_HEADING
            elif is_def:
                seg_type = SegmentType.DEFINITION
            elif num:
                seg_type = SegmentType.CLAUSE
                
            seg_id = self._generate_segment_id(doc_id, start, end)
            
            # Exact substring invariant
            segment_text = full_text[start:end]
            
            segments.append(Segment(
                segment_id=seg_id,
                segment_type=seg_type,
                text=segment_text,
                original_start=start,
                original_end=end,
                processed_start=p_start,
                processed_end=p_end,
                numbering=num,
                sequence=i,
                source_dataset=source_dataset,
                source_document_id=record.original_record.source_document_id,
                contract_id=record.original_record.contract_id,
                existing_clause_id=record.original_record.clause_id
            ))
            
        segments = build_hierarchy(segments)
        
        # Evidence association
        associations = []
        for idx, ev in enumerate(record.evidence):
            if ev.source_field == 'text':
                overlapping = []
                for s in segments:
                    # Check overlap
                    if max(ev.original_start, s.original_start) < min(ev.original_end, s.original_end):
                        overlapping.append(s.segment_id)
                associations.append(EvidenceAssociation(
                    evidence_index=idx,
                    evidence_text=ev.text,
                    overlapping_segment_ids=overlapping
                ))
        
        doc = SegmentedDocument(
            document_id=doc_id,
            source_dataset=source_dataset,
            source_document_id=record.original_record.source_document_id,
            contract_id=record.original_record.contract_id,
            segments=segments,
            segmentation_version=self.version,
            segmentation_config_hash=self.config.config_hash(),
            provenance={"original_record_id": record.original_record.record_id},
            evidence_associations=associations
        )
        
        validate_segments(doc, len(full_text))
        return doc

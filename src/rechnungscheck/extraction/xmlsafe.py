"""Hardened XML parsing for untrusted invoice files.

Invoices come from outside. The parser never resolves entities, never loads
DTDs, never touches the network and rejects any DOCTYPE, which closes XXE,
billion-laughs and SSRF via external entities.
"""

from __future__ import annotations

from lxml import etree

MAX_XML_BYTES = 20 * 1024 * 1024


class UnsafeXmlError(ValueError):
    """The document contains constructs that are never legitimate in an e-invoice."""


_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    dtd_validation=False,
    huge_tree=False,
    remove_comments=True,
    remove_pis=True,
)


def parse_xml(data: bytes) -> etree._Element:
    if len(data) > MAX_XML_BYTES:
        raise UnsafeXmlError(f"XML larger than {MAX_XML_BYTES} bytes")
    head = data[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in data.lower():
        raise UnsafeXmlError("DOCTYPE / ENTITY declarations are not allowed")
    return etree.fromstring(data, _PARSER)

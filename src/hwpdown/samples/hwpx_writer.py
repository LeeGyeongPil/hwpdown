"""Write a synthetic HWPX (OWPML zip) from a SampleDoc. Deterministic: fixed timestamps and order."""
from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

from .hwp5_writer import _sizes
from .spec import P, SampleDoc, T, TB

NS = ('xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
      'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
      'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"')
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
FORMATS = ["DIGIT", "HANGUL_SYLLABLE", "DIGIT", "DIGIT", "DIGIT", "DIGIT", "DIGIT"]  # level 2 -> 가,나,다
EPOCH = (1980, 1, 1, 0, 0, 0)


def _header(sizes: list[float]) -> str:
    chars = "".join(f'<hh:charPr id="{i}" height="{int(round(s * 100))}"/>' for i, s in enumerate(sizes))
    heads = "".join(
        f'<hh:paraHead level="{i + 1}" numFormat="{FORMATS[i]}" start="1">^{i + 1}.</hh:paraHead>' for i in range(7))
    paras = ('<hh:paraPr id="0"><hh:heading type="NONE" idRef="0" level="0"/></hh:paraPr>'
             '<hh:paraPr id="1"><hh:heading type="NUMBER" idRef="1" level="0"/></hh:paraPr>'
             '<hh:paraPr id="2"><hh:heading type="NUMBER" idRef="1" level="1"/></hh:paraPr>')
    return (XML + f'<hh:head {NS} version="1.4"><hh:refList>'
            f'<hh:charProperties itemCnt="{len(sizes)}">{chars}</hh:charProperties>'
            f'<hh:numberings itemCnt="1"><hh:numbering id="1" start="1">{heads}</hh:numbering></hh:numberings>'
            f'<hh:paraProperties itemCnt="3">{paras}</hh:paraProperties></hh:refList></hh:head>')


class _Sec:
    def __init__(self, size_ids: dict[float, int]) -> None:
        self.size_ids = size_ids

    def p(self, p: P) -> str:
        cs = self.size_ids[p.size]
        runs = f'<hp:run charPrIDRef="{cs}"><hp:t>{escape(p.text)}</hp:t></hp:run>' if p.text else ""
        for i, n in enumerate(p.notes):
            inner = "".join(self.p(q) for q in n.paras)
            runs += (f'<hp:run charPrIDRef="{cs}"><hp:ctrl><hp:footNote number="{i + 1}">'
                     f'<hp:subList>{inner}</hp:subList></hp:footNote></hp:ctrl></hp:run>')
        return f'<hp:p paraPrIDRef="{p.shape}" styleIDRef="0">{runs}</hp:p>'

    def tbl(self, t: T) -> str:
        rows = []
        for r in range(t.rows):
            tcs = ""
            for c in sorted((c for c in t.cells if c.row == r), key=lambda c: c.col):
                inner = "".join(self.p(q) for q in c.paras)
                tcs += (f'<hp:tc><hp:subList>{inner}</hp:subList><hp:cellAddr colAddr="{c.col}" rowAddr="{c.row}"/>'
                        f'<hp:cellSpan colSpan="{c.cs}" rowSpan="{c.rs}"/></hp:tc>')
            rows.append(f"<hp:tr>{tcs}</hp:tr>")
        return (f'<hp:p paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0">'
                f'<hp:tbl rowCnt="{t.rows}" colCnt="{t.cols}">{"".join(rows)}</hp:tbl></hp:run></hp:p>')

    def textbox(self, tb: TB) -> str:
        inner = "".join(self.p(q) for q in tb.paras)
        return (f'<hp:p paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0"><hp:rect>'
                f'<hp:drawText><hp:subList>{inner}</hp:subList></hp:drawText></hp:rect></hp:run></hp:p>')

    def section(self, blocks: list) -> str:
        body = ""
        for b in blocks:
            body += self.tbl(b) if isinstance(b, T) else self.textbox(b) if isinstance(b, TB) else self.p(b)
        return XML + f"<hs:sec {NS}>{body}</hs:sec>"


def write_hwpx(doc: SampleDoc) -> bytes:
    """Return the bytes of a synthetic .hwpx document."""
    sizes = _sizes(doc.blocks)
    size_ids = {s: i for i, s in enumerate(sizes)}
    members = [
        ("mimetype", b"application/hwp+zip", zipfile.ZIP_STORED),  # must be the first, uncompressed entry
        ("Contents/header.xml", _header(sizes).encode(), zipfile.ZIP_DEFLATED),
        ("Contents/section0.xml", _Sec(size_ids).section(doc.blocks).encode(), zipfile.ZIP_DEFLATED),
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data, method in members:
            info = zipfile.ZipInfo(name, date_time=EPOCH)
            info.compress_type = method
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return buf.getvalue()


def write_bomb_hwpx(megabytes: int) -> bytes:
    """HWPX whose section0.xml inflates to ``megabytes`` MB of whitespace (compression-bomb test input)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype", date_time=EPOCH), b"application/hwp+zip")
        zi = zipfile.ZipInfo("Contents/section0.xml", date_time=EPOCH)
        zi.compress_type = zipfile.ZIP_DEFLATED
        with z.open(zi, "w", force_zip64=True) as w:
            w.write(f"<hs:sec {NS}>".encode())
            chunk = b" " * (1024 * 1024)
            for _ in range(megabytes):
                w.write(chunk)
            w.write(b"</hs:sec>")
    return buf.getvalue()

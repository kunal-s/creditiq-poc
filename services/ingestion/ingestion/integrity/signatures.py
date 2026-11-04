"""F-07A: a PDF's digital signatures, checked against the file's own bytes.

Ported from fault_detection (`tamper/signatures.py` `verify`, `tamper/integrity.py`
SIGNATURE_PRESENT / SIGNATURE_VALID) with pyHanko (MIT). Offline: nothing is
fetched, revocation is not checked, and the signing time is the signer's own
claim. With no trust list (the default) the signer is named as the certificate
states it and not confirmed; as in fault_detection, trust and the cryptographic
`valid` flag are said, not counted. What counts is whether the signed bytes are
intact and whether anything added after signing is something the signature
permits.

pyHanko does not take two kinds, so they are read from the bytes as
fault_detection does (`_raw_signatures`, `_verify_raw`): the older
adbe.pkcs7.sha1 format, which Indian portals still issue, and a signature no
field points to. The second is usually a remnant: a signed file saved again by
another program (merged, compressed), which drops the field and moves the bytes
so the signature no longer covers the file. fault_detection counts a remnant
as a broken signature; here it is listed for a reader and not counted, because
re-saving a genuine signed document is common and says nothing of its content.
A signature still in its field whose bytes changed counts.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contracts import IntegrityEvidence, IntegrityFinding
from .spec import method

__all__ = ["SIGNATURE_CHECKS", "signature_checks", "verify"]

SIGNATURE_CHECKS = ("SIGNATURE_PRESENT", "SIGNATURE_VALID")
_BYTE_RANGE = re.compile(rb"/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]")

_MODIFICATION_WORDS = {
    "NONE": "nothing has been added since it was signed",
    "LTA_UPDATES": "only validation data has been added since it was signed",
    "FORM_FILLING": "form fields have been filled in since it was signed",
    "ANNOTATIONS": "annotations have been added since it was signed",
    "OTHER": "the content was changed after it was signed",
}


@dataclass(frozen=True, slots=True)
class Signature:
    """One signature as checked."""

    field: str
    signer: str | None
    signed_at: str | None
    intact: bool
    valid: bool
    permitted: bool
    after_signing: str
    trusted: bool | None
    error: str | None = None
    usage_rights: bool = False
    remnant: bool = False
    """Attached to no field and no longer lining up with the file: saved again after signing."""


def trust_roots(directory: str | None) -> list:
    """Root certificates from a folder of PEM or DER files; none unless configured."""
    from asn1crypto import pem, x509  # noqa: PLC0415 - only needed when a file is signed

    if not directory or not Path(directory).is_dir():
        return []
    roots = []
    for path in sorted(Path(directory).iterdir()):
        if path.suffix.lower() not in (".pem", ".crt", ".cer", ".der"):
            continue
        raw = path.read_bytes()
        if pem.detect(raw):
            raw = pem.unarmor(raw)[2]
        roots.append(x509.Certificate.load(raw))
    return roots


def _name(cert) -> str | None:
    try:
        native = cert.subject.native
    except Exception:  # noqa: BLE001
        return None
    return native.get("common_name") or native.get("organization_name")


def verify(data: bytes, roots: list | None = None) -> tuple[list[Signature], int]:
    """Every signature pyHanko reads, checked; and how many signatures the bytes
    hold that it did not read."""
    from pyhanko.pdf_utils.reader import PdfFileReader  # noqa: PLC0415
    from pyhanko.sign.diff_analysis import ModificationLevel  # noqa: PLC0415
    from pyhanko.sign.validation import async_validate_pdf_signature  # noqa: PLC0415
    from pyhanko_certvalidator import ValidationContext  # noqa: PLC0415

    for name in ("pyhanko", "pyhanko_certvalidator"):
        logging.getLogger(name).setLevel(logging.CRITICAL)   # its tracebacks are said in the finding
    roots = roots or []
    raws = _raw_signatures(data)
    out: list[Signature] = []
    handled: set[tuple] = set()
    in_fields: set[tuple] = set()
    embedded = []
    try:
        reader = PdfFileReader(io.BytesIO(data), strict=False)
        if reader.encrypted:
            reader.decrypt(b"")  # locked against editing only: the opening password is empty
        from pyhanko.sign.fields import enumerate_sig_fields  # noqa: PLC0415
        in_fields = {tuple(int(v) for v in value.get_object()["/ByteRange"])
                     for _, value, _ in enumerate_sig_fields(reader, filled_status=True) if value is not None}
        embedded = list(reader.embedded_signatures)
    except Exception:  # noqa: BLE001 - the bytes are read below
        pass
    for sig in embedded:
        field = sig.field_name or "signature"
        try:
            handled.add(tuple(int(v) for v in sig.sig_object["/ByteRange"]))
        except Exception:  # noqa: BLE001
            pass
        usage = "/UR3" in str(sig.sig_object.get("/Reference", ""))
        try:
            claimed = sig.self_reported_timestamp
            context = ValidationContext(trust_roots=roots, allow_fetching=False, revocation_mode="soft-fail",
                                        **({"moment": claimed} if claimed else {}))
            status = _on_own_loop(lambda: async_validate_pdf_signature(sig, context))
        except Exception as exc:  # noqa: BLE001 - said, never passed
            out.append(Signature(field, None, None, False, False, False, "", None,
                                 error=f"could not be verified: {type(exc).__name__}", usage_rights=usage))
            continue
        diff = status.diff_result
        level = getattr(diff, "modification_level", None)
        if level is None:
            # Changes the comparison could not justify come back as the error describing them.
            changed = len(re.findall(r"Reference\(idnum=", str(diff or "")))
            permitted = False
            after = ("the content was changed after it was signed — a revision added later "
                     + (f"replaces {changed} part(s) of the document" if changed else "changes the document")
                     + " in a way the signature does not allow")
        else:
            permitted = bool(status.docmdp_ok) and level is not ModificationLevel.OTHER
            after = _MODIFICATION_WORDS.get(level.name, level.name.lower())
        trusted = None if not roots else status.trust_problem_indic is None
        out.append(Signature(field, _name(status.signing_cert), claimed.isoformat() if claimed else None,
                             bool(status.intact), bool(status.valid), permitted, after, trusted,
                             usage_rights=usage))
    unread = 0
    for raw in raws:
        if raw["byte_range"] in handled:
            continue
        checked = _verify_raw(data, raw, orphaned=raw["byte_range"] not in in_fields)
        if checked is None:
            unread += 1
        else:
            out.append(checked)
    return out, unread


def _on_own_loop(make):
    """pyHanko validates asynchronously, and its plain call starts an event loop of
    its own, which fails inside one already running (the service's). Run it on a
    loop of its own, in a thread of its own."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(make())).result()


def _raw_signatures(data: bytes) -> list[dict]:
    """Every signature dictionary, read from the bytes. A signature keeps its byte
    ranges and its value in plain bytes (the value is the one hole the ranges
    leave), whether or not any field still points at it."""
    out = []
    for m in _BYTE_RANGE.finditer(data):
        # This signature's own object, and nothing beside it.
        start = data.rfind(b" obj", 0, m.start())
        end = data.find(b"endobj", m.end())
        window = data[max(0, start):end if end != -1 else m.end() + 20000]
        contents = re.search(rb"/Contents\s*<([0-9A-Fa-f\s]+)>", window)
        if not contents:
            continue
        subfilter = re.search(rb"/SubFilter\s*/([A-Za-z0-9.]+)", window)
        claimed = re.search(rb"/M\s*\(D:(\d{14})", window)
        out.append({"byte_range": tuple(int(v) for v in m.groups()),
                    "contents": bytes.fromhex(re.sub(rb"\s", b"", contents.group(1)).decode()),
                    "subfilter": subfilter.group(1).decode() if subfilter else None,
                    "claimed": claimed.group(1).decode() if claimed else None,
                    "usage_rights": re.search(rb"/TransformMethod\s*/UR3?(?![A-Za-z0-9])", window) is not None})
    return out


def _verify_raw(data: bytes, raw: dict, *, orphaned: bool) -> Signature | None:
    """One signature checked from its own bytes (fault_detection `_verify_raw`):
    the ranges still describe this file, the covered bytes hash to what was
    signed, and the value verifies with the signer's key. None when the value
    cannot be read at all."""
    from asn1crypto import cms  # noqa: PLC0415
    from cryptography import x509 as cx509  # noqa: PLC0415
    from cryptography.hazmat.primitives import hashes  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa  # noqa: PLC0415

    a, b, c, d = raw["byte_range"]
    fmt, claimed = raw["subfilter"], raw["claimed"]
    signed_at = (f"{claimed[0:4]}-{claimed[4:6]}-{claimed[6:8]}T{claimed[8:10]}:{claimed[10:12]}:{claimed[12:14]}"
                 if claimed else None)
    usage = bool(raw["usage_rights"])
    orphaned = orphaned and not usage   # a usage-rights signature is never in a field
    # The hole between the ranges must be exactly this signature's value: a file
    # saved again moves everything, and the ranges then point at other bytes.
    in_bounds = a == 0 and b > 0 and c > b and c + d <= len(data)
    aligned = in_bounds and data[b:b + 1] == b"<" and data[c - 1:c] == b">"
    try:
        info = cms.ContentInfo.load(raw["contents"], strict=False)
        signed = info["content"]
        signer_info = signed["signer_infos"][0]
        certs = [cc.chosen for cc in signed["certificates"] if cc.name == "certificate"]
        sid = signer_info["sid"]
        serial = sid.chosen["serial_number"].native if sid.name == "issuer_and_serial_number" else None
        cert = next((cc for cc in certs if serial is not None and cc.serial_number == serial), certs[0])
    except Exception:  # noqa: BLE001 - a value that cannot be read is said, not judged
        return None
    hash_name = signer_info["digest_algorithm"]["algorithm"].native
    algo = {"sha1": hashes.SHA1(), "sha256": hashes.SHA256(), "sha384": hashes.SHA384(),
            "sha512": hashes.SHA512()}.get(hash_name, hashes.SHA256())
    covered = data[a:a + b] + data[c:c + d] if in_bounds else b""
    attrs = signer_info["signed_attrs"]
    econtent = signed["encap_content_info"]["content"]
    if fmt == "adbe.pkcs7.sha1":
        # The signed content is itself the SHA-1 of the covered bytes.
        signed_content = econtent.native if econtent.native is not None else b""
        intact = aligned and signed_content == hashlib.sha1(covered).digest()
    else:
        signed_content = None
        digest = next((at["values"][0].native for at in attrs if at["type"].native == "message_digest"),
                      None) if attrs else None
        h = hashlib.new(hash_name if hash_name in hashlib.algorithms_available else "sha256")
        h.update(covered)
        intact = aligned and digest == h.digest()
    to_verify = (b"\x31" + attrs.dump()[1:]) if attrs else (signed_content or b"")
    try:
        key = cx509.load_der_x509_certificate(cert.dump()).public_key()
        value = signer_info["signature"].native
        if isinstance(key, rsa.RSAPublicKey):
            key.verify(value, to_verify, padding.PKCS1v15(), algo)
        elif isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(value, to_verify, ec.ECDSA(algo))
        else:
            raise ValueError("unsupported key type")
        valid = True
    except Exception:  # noqa: BLE001 - a failed verification is the answer
        valid = False
    tail = len(data[c + d:].strip(b" \t\r\n\x00\x0b\x0c")) if in_bounds else 0
    if not aligned:
        after = "the file was saved again after it was signed, so the signature no longer covers it"
    elif tail:
        after = "a later revision was added after signing; this format leaves it unanalysed"
    else:
        after = _MODIFICATION_WORDS["NONE"]
    if fmt == "adbe.pkcs7.sha1" or hash_name == "sha1":
        after += " (it uses SHA-1, no longer considered strong against a deliberate forgery)"
    return Signature("usage rights" if usage else "signature", _name(cert), signed_at, intact, valid,
                     # A later revision this format cannot analyse is neither permitted
                     # nor condemned: only a broken signature counts.
                     True, after, None, usage_rights=usage, remnant=orphaned and not aligned)


def _result(cfg: dict, code: str, status: str, finding: str,
            evidence: list[IntegrityEvidence] | None = None, failed: bool = False) -> IntegrityFinding:
    spec = cfg["checks"][code]
    return IntegrityFinding(code=code, family=spec["family"], status=status, finding=finding,
                            evidence=evidence or [], tier=spec["tier"], impact=spec["impact"],
                            context=bool(spec.get("context", False)),
                            method=method(spec, cfg["version"], failed=failed), reads=["signatures"])


def signature_checks(cfg: dict[str, Any], data: bytes) -> list[IntegrityFinding]:
    """SIGNATURE_PRESENT (context) and SIGNATURE_VALID (T0)."""
    if not any(c in cfg["checks"] for c in SIGNATURE_CHECKS):
        return []
    none = "The file carries no digital signature. A picture of a signature on the page is not one."
    if not _BYTE_RANGE.search(data):
        # A signature keeps its byte range in plain bytes (its offsets must be readable
        # without parsing the file), so a file without one is not signed: said without
        # asking a strict reader to parse a loosely written file.
        return [_result(cfg, c, "not_applicable", none) for c in SIGNATURE_CHECKS if c in cfg["checks"]]
    try:
        found, unread = verify(data, trust_roots((cfg.get("signatures") or {}).get("trust_roots")))
    except Exception as e:  # noqa: BLE001 - said on both checks, never passed
        why = f"The signatures could not be read: {type(e).__name__}."
        return [_result(cfg, c, "unable_to_determine", why, failed=True) for c in SIGNATURE_CHECKS
                if c in cfg["checks"]]
    sigs = [s for s in found if not s.usage_rights]
    out: list[IntegrityFinding] = []
    if not sigs and not unread:
        if found:
            none = ("The file carries no issuer's signature: its only signature is a usage-rights signature, which "
                    "a forms server applies to unlock features in a PDF reader and which says nothing about who "
                    "issued it.")
        return [_result(cfg, c, "not_applicable", none) for c in SIGNATURE_CHECKS if c in cfg["checks"]]
    signers = ", ".join(s.signer or "an unnamed signer" for s in sigs)
    said = (f"{len(sigs)} digital signature(s){': ' + signers if sigs else ''}"
            + (f"; {unread} more in a form that could not be verified" if unread else "") + ".")
    out.append(_result(cfg, "SIGNATURE_PRESENT", "pass", said,
                       [IntegrityEvidence(page=1, observed=f"{s.signer or s.field}, signed {s.signed_at or 'at no stated time'}",
                                          threshold="a digital signature in the file") for s in sigs]))
    # A signature that could not be checked is said so, never taken as broken.
    unchecked = [s for s in sigs if s.error]
    broken = [s for s in sigs if not s.error and (not s.intact or not s.permitted) and not s.remnant]
    remnants = [s for s in sigs if s.remnant]
    if broken:
        s = broken[0]
        why = "its signed bytes no longer match" if not s.intact else f"after signing, {s.after_signing}"
        out.append(_result(cfg, "SIGNATURE_VALID", "review_required", f"A signature does not hold: {why}.",
                           [IntegrityEvidence(page=1, observed=f"{b.signer or b.field}: bytes intact "
                                                               f"{'yes' if b.intact else 'no'}; what was added after "
                                                               f"signing {'is' if b.permitted else 'is not'} permitted"
                                                               + (f" ({b.error})" if b.error else ""),
                                              threshold="the signed bytes unchanged, nothing unpermitted added")
                            for b in broken]))
    elif not sigs or unchecked:
        out.append(_result(cfg, "SIGNATURE_VALID", "unable_to_determine",
                           f"{len(unchecked) + unread} signature(s) could not be verified"
                           + (f" ({unchecked[0].error})" if unchecked else ": they are in a form that is not read")
                           + "; nothing is said about whether they hold."))
    elif remnants:
        hit = _result(cfg, "SIGNATURE_VALID", "warning",
                      f"{len(remnants)} signature(s) remain from the signed original, but the file was saved again "
                      f"after signing, so they no longer cover this file: what it shows now is not what was signed.",
                      [IntegrityEvidence(page=1, observed=f"{r.signer or r.field}: signed "
                                                          f"{r.signed_at or 'at no stated time'}; {r.after_signing}",
                                         threshold="a signature that covers the file as it is")
                       for r in remnants])
        out.append(hit.model_copy(update={"context": True}))
    else:
        trust = ("its signer is on the trust list" if all(s.trusted for s in sigs)
                 else "no trust list confirms who signed" if any(s.trusted is None for s in sigs)
                 else "its signer is not on the trust list")
        out.append(_result(cfg, "SIGNATURE_VALID", "pass",
                           "Every signature covers its bytes intact and nothing unpermitted was added after it; "
                           f"{trust}" + (f"; {unread} more could not be verified" if unread else "") + "."))
    return [f for f in out if f.code in cfg["checks"]]

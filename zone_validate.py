# Standard library modules
import string
import re


class ValidateError(Exception):
    """Class for exceptions"""

    def __init__(self, message, content):
        self.message = message
        self.content = content


def is_valid_label(label, strict=True):
    """Checks that label is valid"""
    # Can't be too short or long
    if not (1 <= len(label) <= 63):
        return False
    if not strict:
        return True
    # May not start with a number
    if label[0] in string.digits:
        return False
    # May not end with a hyphen
    if label.endswith("-"):
        return False
    # Check for forbidden characters
    match = re.search(r"[^a-zA-Z0-9-]", label)
    return match is None


def is_valid_domain(domain, strict=True):
    """Check for validity of domain as specified in RFC1035"""
    if not (1 <= len(domain) <= 255):
        return False
    if domain == ".":
        # "." is valid in some contexts
        return True
    if domain.endswith("."):
        domain = domain[:-1]
    for label in domain.split("."):
        if not is_valid_label(label, strict=strict):
            return False
    return True


def is_valid_name(name, strict=True):
    """Check validity of a hostname"""
    if name in ["@", "*"]:
        # Special cases
        return True
    return is_valid_domain(name, strict=strict)


def is_valid_target(name, strict=False):
    """Check that the target of a RR is valid"""
    if strict and not name.endswith("."):
        print(
            "*** Warning: target {} is missing a terminating dot".format(name)
        )
    return is_valid_domain(name)


def is_valid_ttl(ttl):
    """Check that ttl value is valid (ie. positive signed 32 bit number)"""
    if len(ttl) == 0:
        return False
    match = re.search(r"[^0-9]", ttl)
    if match is not None:
        return False
    value = int(ttl)
    if not (0 <= value < 2 ** 31):
        return False
    return True


def is_valid_uint16(s):
    if len(s) == 0:
        return False
    match = re.search(r"[^0-9]", s)
    if match is not None:
        return False
    value = int(s)
    if not (0 <= value < 2 ** 16):
        return False
    return True


def is_valid_uint8(s):
    if len(s) == 0:
        return False
    match = re.search(r"[^0-9]", s)
    if match is not None:
        return False
    value = int(s)
    if not (0 <= value < 2 ** 8):
        return False
    return True


def is_valid_hex(s):
    if len(s) == 0:
        return False
    match = re.search(r"[^0-9a-f]", s.lower())
    return match is None


def is_valid_mx(preference, exchange):
    """Check an MX record"""
    # preference should be an unsigned 16 bit integer
    return is_valid_uint16(preference) and is_valid_target(
        exchange, strict=True
    )


def is_valid_ipv4(address):
    """Check an IPv4 address for validity"""
    octets = address.split(".")
    if len(octets) != 4:
        return False
    for o in octets:
        try:
            value = int(o)
        except ValueError:
            return False
        if not (0 <= value <= 255):
            return False
    return True


def is_valid_ipv6(address):
    """Check an IPv6 address for validity"""
    groups = address.split(":")
    if len(groups) < 3:
        # minimum is abcd::1
        return False
    if len(groups) > 8:
        return False
    gap = False
    for h in groups:
        if len(h) == 0:
            if gap:
                return False
            gap = True
        else:
            try:
                value = int(h, base=16)
            except ValueError:
                return False
            if not (0 <= value <= 0xFFFF):
                return False
    if len(groups) < 8 and not gap:
        return False
    return True


def tokenize(line):
    tokens = []
    tok = ""
    quoted = False
    for c in line:
        if quoted:
            tok += c
            if c == '"':
                quoted = False
        elif c in [" ", "\t"]:
            if len(tok) > 0:
                tokens.append(tok)
                tok = ""
            elif len(tokens) == 0:
                tokens.append("")
        else:
            if c == '"':
                quoted = True
            if c == ";":
                break
            tok += c
    if quoted:
        raise ValidateError("Unclosed quotes", line)
    if tok:
        tokens.append(tok)
    return tokens


def skip_zone_record(zone_record):
    """Whether a zone record should be skipped or not.

    Records are skipped if they are empty or start with
    a # (indicating a comment).

    :param zone_record: Full zone record, including the command (e.g. ADD).
    :returns: True if the record should be skipped, false otherwise.
    """
    zone_record = zone_record.strip()

    return not zone_record or zone_record[:1] == "#"


def validate_zone_record(zone_record, strict=False):
    """Validate a zone record.

    This validation is not exhaustive and may allow some invalid
    records through (false positive) or reject valid records (false
    negative). It is mainly intended to catch common errors, although
    in time it will be expanded.

    :param zone_record: Full zone record, including the command (e.g. ADD).
    :returns: True if the record appears valid, false otherwise.
    """
    valid_commands = ["ADD", "DELETE", "REPLACE"]
    non_strict_types = ["TXT", "SRV"]

    if skip_zone_record(zone_record):
        return True
    else:
        # Looks like an actual record
        zone_record = zone_record.strip()
        try:
            zone_record_parts = tokenize(zone_record)
        except ValidateError as err:
            print("*", err.message)
            return False

        if len(zone_record_parts) >= 5:
            # First four fields are the same for all records
            (
                record_command,
                record_hostname,
                record_ttl,
                record_type,
                *record_data,
            ) = zone_record_parts
            record_type = record_type.upper()

            strict_name = record_type not in non_strict_types

            if record_command not in valid_commands:
                return False
            if not is_valid_ttl(record_ttl):
                return False
            if not is_valid_name(record_hostname, strict_name):
                return False

            fields = len(record_data)
            if record_type in ["CNAME", "ANAME", "NS"]:
                return (fields == 1) and is_valid_target(
                    record_data[0], strict=strict
                )
            if record_type == "SOA":
                return (
                    (fields == 7)
                    and is_valid_target(record_data[0], strict=True)
                    and is_valid_target(record_data[1], strict=True)
                    and is_valid_ttl(record_data[2])
                    and is_valid_ttl(record_data[3])
                    and is_valid_ttl(record_data[4])
                    and is_valid_ttl(record_data[5])
                    and is_valid_ttl(record_data[6])
                )
            elif record_type == "A":
                return (fields == 1) and is_valid_ipv4(record_data[0])
            elif record_type == "AAAA":
                return (fields == 1) and is_valid_ipv6(record_data[0])
            elif record_type == "TXT":
                if fields == 0:
                    return False
                if fields > 1 and strict:
                    print("* Warning: TXT record has multiple parts")
                    print(zone_record)
                return True
            elif record_type == "MX":
                if fields != 2:
                    return False
                priority, host = record_data
                return is_valid_mx(priority, host)
            elif record_type == "SRV":
                if fields != 4:
                    return False
                priority, weight, port, target = record_data
                return (
                    is_valid_uint16(priority)
                    and is_valid_uint16(weight)
                    and is_valid_uint16(port)
                    and is_valid_target(target, strict=strict)
                    and record_hostname.startswith("_")
                )
            elif record_type == "CAA":
                if fields != 3:
                    return False
                flags, tag, value = record_data
                if tag.lower() not in ["issue", "issuewild", "iodef"]:
                    return False
                # not checking value, which is arbitrary text
                return is_valid_uint8(flags)
            elif record_type == "SSHFP":
                if fields != 3:
                    return False
                algorithm, fingerprint_type, fingerprint = record_data
                return (
                    is_valid_uint8(algorithm)
                    and is_valid_uint8(fingerprint_type)
                    and is_valid_hex(fingerprint)
                )
            else:
                print("Cannot validate type {}".format(record_type))
                return not strict

    return False

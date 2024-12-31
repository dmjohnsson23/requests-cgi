from dataclasses import dataclass
from enum import IntEnum, IntFlag
from struct import Struct

__all__ = ('FASTCGI_VERSION','Role','RecordType','State','RecordHeader','Record','NameValue','BeginRequestOptions','BeginRequestBody')

# See https://fastcgi-archives.github.io/FastCGI_Specification.html

FASTCGI_VERSION = 1

class Role(IntEnum):
    responder = 1
    authorizer = 2
    filter = 3


class RecordType(IntEnum):
    begin = 1
    abort = 2
    end = 3
    params = 4
    stdin = 5
    stdout = 6
    stderr = 7
    data = 8
    get_values = 9
    get_values_result = 10
    unknown_type = 11


class State(IntEnum):
    send = 1
    error = 2
    success = 3


# Specs: https://fastcgi-archives.github.io/FastCGI_Specification.html#S3.3
_HEADER_STRUCT = Struct(">BBHHBx")
@dataclass
class RecordHeader:
    version: int
    type: RecordType
    request_id: int # value 0 reserved for management records; values 1-0xffff allowed
    content_length: int
    padding_length: int

    @classmethod
    def decode(cls, data: bytes):
        return cls(*_HEADER_STRUCT.unpack(data))
    
    def encode(self)->bytes:
        return _HEADER_STRUCT.pack(
            self.version, 
            self.type, 
            self.request_id, 
            self.content_length, 
            self.padding_length, 
        )


@dataclass
class Record:
    header: RecordHeader
    content: bytes

    @classmethod
    def create(cls, fcgi_type: RecordType, content: bytes, req_id: int):
        # The spec recommends padding to make the full record length a multiple of 8 bytes. This 
        # is supposedly a performance thing. However, in practice I actually got worse performance 
        # when I tried it. Anyway, performance seems perfectly fine with or without padding. And I 
        # also doubt this library will ever reach the level of optimization where tweaks like that 
        # would be impactful.
        header = RecordHeader(
            FASTCGI_VERSION,
            fcgi_type,
            req_id,
            len(content),
            0,
        )
        return cls(header, content)
    
    @classmethod
    def read_from_stream(cls, stream):
        header = stream.read(_HEADER_STRUCT.size)
        if not header:
            return None
        header = RecordHeader.decode(header)

        content = bytearray()
        bytes_read = 0
        while bytes_read < header.content_length:
            buffer = stream.read(header.content_length - bytes_read)
            if not buffer:
                break
            bytes_read += len(buffer)
            content += buffer
        # TODO not sure why we need all that above to fully capture the regular content, but not the padding...
        stream.read(header.padding_length)
        return cls(header, content)

    def encode(self)->bytes:
        return b''.join((self.header.encode(), self.content, bytes(self.header.padding_length)))


# Specs: https://fastcgi-archives.github.io/FastCGI_Specification.html#S3.4
_UNSIGNED_LONG_STRUCT = Struct(">L")
@dataclass
class NameValue:
    name: bytes
    value: bytes

    def encode(self):
        len_name = len(self.name)
        len_value = len(self.value)
        lengths = bytearray()
        if len_name < 128:
            lengths.append(len_name)
        else:
            lengths.extend(_UNSIGNED_LONG_STRUCT.pack(len_name | 0x80_00_00_00))
        if len_value < 128:
            lengths.append(len_value)
        else:
            lengths.extend(_UNSIGNED_LONG_STRUCT.pack(len_value | 0x80_00_00_00))
        return lengths + self.name + self.value


class BeginRequestOptions(IntFlag):
    keep_connection = 0b00000001


# Specs: https://fastcgi-archives.github.io/_Specification.html#S5.1
_BEGIN_REQUEST_STRUCT = Struct(">HBxxxxx")
@dataclass
class BeginRequestBody:
    role: Role
    flags: BeginRequestOptions = BeginRequestOptions(0)

    def encode(self):
        return _BEGIN_REQUEST_STRUCT.pack(self.role, self.flags)
"""Шифрование cookie-профилей.

Ключ Fernet генерируется один раз и хранится в LOCALAPPDATA\\Zephyrus\\data\\vault.key.
В Windows сам ключ дополнительно защищён DPAPI (привязан к учётной записи пользователя),
поэтому скопированные файлы профилей на другой машине / под другим пользователем не расшифровать.
На других ОС ключ лежит в файле с правами 0600.
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_IS_WIN = sys.platform.startswith("win")


if _IS_WIN:
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_Blob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(_Blob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]

    def _dpapi(data: bytes, protect: bool) -> bytes:
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = _Blob()
        if protect:
            ok = _crypt32.CryptProtectData(ctypes.byref(blob_in), "Zephyrus", None, None, None, 0, ctypes.byref(blob_out))
        else:
            ok = _crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
        if not ok:
            raise OSError(f"DPAPI error {ctypes.get_last_error()}")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            _kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))

    def _protect(raw: bytes) -> bytes:
        return _dpapi(raw, True)

    def _unprotect(raw: bytes) -> bytes:
        return _dpapi(raw, False)
else:
    def _protect(raw: bytes) -> bytes:
        return raw

    def _unprotect(raw: bytes) -> bytes:
        return raw


class VaultError(Exception):
    pass


class Vault:
    def __init__(self, key_path: Path) -> None:
        self._key_path = key_path
        self._fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if self._key_path.exists():
            try:
                return _unprotect(self._key_path.read_bytes())
            except OSError as exc:
                raise VaultError("Не удалось расшифровать ключ хранилища (другой пользователь Windows?)") from exc
        key = Fernet.generate_key()
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_path.write_bytes(_protect(key))
        try:
            os.chmod(self._key_path, 0o600)
        except OSError:
            pass
        return key

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        try:
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise VaultError("Файл профиля повреждён или зашифрован другим ключом") from exc

# -*- coding: utf-8 -*-
"""Google Drive core (resources/lib/gdrive.py) against a fake Google: sign-in, refresh, folders, upload/download, merge"""
import base64
import json

import pytest

from resources.lib import gdrive


class Resp(object):
    def __init__(self, status=200, body=None, headers=None, content=b''):
        self.status_code, self._body, self.headers, self._content = status, body, headers or {}, content

    def json(self):
        return self._body if self._body is not None else {}

    def iter_content(self, n):
        yield self._content


class FakeGoogle(object):
    """just enough of oauth2 + drive v3 to exercise every code path"""
    def __init__(self):
        self.files = {}                    # id -> {name, parents, mimeType, data}
        self.pending = 2                   # polls before the user approves
        self.valid = set()
        self.calls = []
        self.n = 0

    def _id(self):
        self.n += 1
        return 'f%d' % self.n

    def _auth(self, headers):
        return (headers or {}).get('Authorization', '').replace('Bearer ', '') in self.valid

    def post(self, url, data=None, json=None, params=None, headers=None, timeout=None):
        self.calls.append(('post', url))
        if url == gdrive.DEVICE_URL:
            return Resp(200, {'device_code': 'DEV', 'user_code': 'ABCD-EFGH', 'verification_url': 'https://www.google.com/device',
                              'interval': 5, 'expires_in': 1800})
        if url == gdrive.TOKEN_URL:
            if data.get('grant_type', '').endswith('device_code'):
                if self.pending:
                    self.pending -= 1
                    return Resp(428, {'error': 'authorization_pending'})
                idt = 'x.' + base64.urlsafe_b64encode(b'{"email":"me@gmail.com"}').decode().rstrip('=') + '.y'
                self.valid.add('AT1')
                return Resp(200, {'access_token': 'AT1', 'refresh_token': 'RT', 'expires_in': 3600, 'id_token': idt})
            if data.get('refresh_token') == 'RT':
                tok = 'AT%d' % (len(self.valid) + 1)
                self.valid.add(tok)
                return Resp(200, {'access_token': tok, 'expires_in': 3600})
            return Resp(400, {'error': 'invalid_grant'})
        if url == gdrive.REVOKE_URL:
            return Resp(200, {})
        if not self._auth(headers):
            return Resp(401, {'error': {'message': 'auth'}})
        if url == gdrive.API + '/files':            # create folder
            fid = self._id()
            self.files[fid] = dict(json, data=b'')
            return Resp(200, {'id': fid})
        if url == gdrive.UPLOAD and params.get('uploadType') == 'multipart':
            meta, payload = self._multipart(data, headers)
            fid = self._id()
            self.files[fid] = dict(meta, mimeType='application/octet-stream', data=payload)
            return Resp(200, {'id': fid})
        if url == gdrive.UPLOAD and params.get('uploadType') == 'resumable':
            fid = self._id()
            self.files[fid] = dict(json, mimeType='application/zip', data=b'')
            self.sessions = getattr(self, 'sessions', {})
            self.sessions['https://upload/session/' + fid] = (fid, int(headers['X-Upload-Content-Length']))
            return Resp(200, {}, headers={'Location': 'https://upload/session/' + fid})
        raise AssertionError(url)

    def put(self, url, data=None, headers=None, timeout=None):
        fid, total = self.sessions[url]
        rng = headers['Content-Range'].split(' ')[1]
        start = int(rng.split('-')[0])
        assert start == len(self.files[fid]['data'])          # chunks arrive in order, none lost
        self.files[fid]['data'] += data
        if len(self.files[fid]['data']) < total:
            return Resp(308, {})
        return Resp(200, {'id': fid})

    def patch(self, url, data=None, params=None, headers=None, timeout=None, json=None):
        if not self._auth(headers):
            return Resp(401, {})
        fid = url.rsplit('/', 1)[1]
        meta, payload = self._multipart(data, headers)
        self.files[fid]['data'] = payload
        return Resp(200, {'id': fid})

    @staticmethod
    def _multipart(data, headers):
        boundary = headers['Content-Type'].split('boundary=')[1].encode()
        parts = data.split(b'--' + boundary)
        meta = json.loads(parts[1].split(b'\r\n\r\n', 1)[1].strip())
        payload = parts[2].split(b'\r\n\r\n', 1)[1][:-2]
        return meta, payload

    def get(self, url, params=None, headers=None, timeout=None, stream=False):
        if not self._auth(headers):
            return Resp(401, {})
        if url == gdrive.API + '/files':
            q = params['q']
            parent = q.split("'")[1]
            out = [dict(id=i, name=f['name'], mimeType=f['mimeType'], size=str(len(f['data'])), modifiedTime='2026-09-29T10:00:%02d' % int(i[1:]))
                   for i, f in self.files.items() if parent in f.get('parents', [])]
            if "name='" in q:
                name = q.split("name='")[1].split("'")[0]
                out = [f for f in out if f['name'] == name]
            if 'folder' in q.split('mimeType=')[-1] and 'mimeType=' in q:
                out = [f for f in out if f['mimeType'] == gdrive.FOLDER]
            return Resp(200, {'files': sorted(out, key=lambda f: f['modifiedTime'], reverse=True)})
        if url == gdrive.API + '/about':
            return Resp(200, {'storageQuota': {'usage': '100', 'limit': '1000'}})
        fid = url.rsplit('/', 1)[1]
        return Resp(200, content=self.files[fid]['data'])

    def delete(self, url, headers=None, timeout=None):
        if not self._auth(headers):
            return Resp(401, {})
        self.files.pop(url.rsplit('/', 1)[1])
        return Resp(204, {})


@pytest.fixture
def g(tmp_path):
    fake = FakeGoogle()
    clock = [1000.0]
    d = gdrive.Drive('CID', 'SECRET', str(tmp_path / 'tok.json'), http=fake, clock=lambda: clock[0])
    return d, fake, clock, tmp_path


def _signin(d):
    info = d.start_login()
    while not d.poll_login(info['device_code']):
        pass
    return info


def test_device_sign_in(g):
    d, fake, clock, _ = g
    assert not d.signed_in()
    info = _signin(d)
    assert info['user_code'] == 'ABCD-EFGH' and 'google.com/device' in info['verification_url']
    assert d.signed_in() and d.account() == 'me@gmail.com'


def test_not_signed_in_raises(g):
    d = g[0]
    with pytest.raises(gdrive.NotSignedIn):
        d.folder()


def test_no_client_configured(tmp_path):
    with pytest.raises(gdrive.DriveError):
        gdrive.Drive('', '', str(tmp_path / 't.json'), http=FakeGoogle()).start_login()


def test_folders_created_once_and_reused(g):
    d, fake, _, _ = g
    _signin(d)
    a = d.folder('Backups')
    d._folders = {}                                       # a new session finds them instead of creating twins
    assert d.folder('Backups') == a
    names = sorted(f['name'] for f in fake.files.values())
    assert names == ['BN Stream', 'Backups']


def test_upload_download_replace_delete(g):
    d, fake, _, tmp = g
    _signin(d)
    src = tmp / 'a.json'
    src.write_text('{"v": 1}', encoding='utf-8')
    folder = d.folder('Sync')
    fid = d.upload(str(src), folder, 'a.json', 'application/json')
    src.write_text('{"v": 2}', encoding='utf-8')
    assert d.upload(str(src), folder, 'a.json', 'application/json', replace=True) == fid     # overwritten, not doubled
    assert len(d.list(folder, name='a.json')) == 1
    out = tmp / 'b.json'
    d.download(fid, str(out))
    assert json.loads(out.read_text(encoding='utf-8')) == {'v': 2}
    d.delete(fid)
    assert d.list(folder) == []


def test_token_refresh_when_expired(g):
    d, fake, clock, _ = g
    _signin(d)
    d.folder()
    clock[0] += 7200                                      # access token expired
    d.folder('Backups')
    assert any(c == ('post', gdrive.TOKEN_URL) for c in fake.calls[-4:])


def test_revoked_sign_in_asks_to_sign_in_again(g):
    d, fake, clock, _ = g
    _signin(d)
    d._save(dict(d._load(), refresh_token='REVOKED', expires=0))
    with pytest.raises(gdrive.NotSignedIn):
        d.folder()
    assert not d.signed_in()


def test_logout(g):
    d = g[0]
    _signin(d)
    d.logout()
    assert not d.signed_in()


def test_prune_keeps_newest():
    files = [{'name': 'BN-backup-%d.zip' % i} for i in (5, 4, 3, 2, 1)] + [{'name': 'notes.txt'}]
    assert [f['name'] for f in gdrive.prune(files, 3)] == ['BN-backup-2.zip', 'BN-backup-1.zip']


def test_merge_favourites_union_and_removals():
    a = [{'kind': 'movie', 'id': 1, 'added': '01/10/2026 10:00'}, {'kind': 'movie', 'id': 2, 'added': '29/09/2026 10:00'}]
    b = [{'kind': 'movie', 'id': 2, 'added': '29/09/2026 10:00'}, {'kind': 'series', 'id': 7, 'added': '30/09/2026 12:00'}]
    removed = [{'kind': 'movie', 'id': 2, 'removed': '30/09/2026 09:00'}]
    out = gdrive.merge_favourites(a, b, removed)
    assert [(f['kind'], f['id']) for f in out] == [('movie', 1), ('series', 7)]      # 01/10 sorts after 30/09


def test_readded_after_removal_stays():
    fav = [{'kind': 'movie', 'id': 2, 'added': '02/10/2026 10:00'}]
    assert gdrive.merge_favourites(fav, [], [{'kind': 'movie', 'id': 2, 'removed': '30/09/2026 09:00'}]) == fav


def test_merge_history_latest_wins():
    a = [{'key': 'tv:1:1:1', 'when': '29/09/2026 20:00'}]
    b = [{'key': 'tv:1:1:1', 'when': '01/10/2026 08:00'}, {'key': 'movie:5', 'when': '30/09/2026 21:00'}]
    out = gdrive.merge_history(a, b)
    assert [(h['key'], h['when']) for h in out] == [('tv:1:1:1', '01/10/2026 08:00'), ('movie:5', '30/09/2026 21:00')]


def test_big_file_resumable_upload_in_chunks(g, monkeypatch):
    d, fake, _, tmp = g
    _signin(d)
    monkeypatch.setattr(gdrive, 'SIMPLE_MAX', 10)
    monkeypatch.setattr(gdrive, 'CHUNK', 7)
    big = tmp / 'BN-backup-1.zip'
    payload = bytes(range(256)) * 3                       # 768 bytes -> 110 chunks of 7
    big.write_bytes(payload)
    fid = d.upload(str(big), d.folder('Backups'), big.name, 'application/zip')
    assert fake.files[fid]['data'] == payload

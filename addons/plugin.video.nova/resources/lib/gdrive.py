# -*- coding: utf-8 -*-
"""Google Drive for BN Stream: sign in with a code on the TV, backups, sync and a "BN Stream" folder.

Scope drive.file: the build sees only files it created itself (Google's rule for sign-in with a code on a TV;
the whole Drive would need a restricted scope). Everything lives under "BN Stream/" in the viewer's Drive:
  BN Stream/Backups    full BN backups (backup.make_zip)
  BN Stream/Sync       favourites / history / IPTV sources / sources on-off, merged between devices
  BN Stream/Subtitles  the subtitle store (every created subtitle)

The OAuth client ("TVs and Limited Input devices") belongs to the build owner: settings gd_client_id /
gd_client_secret, filled by make_build from work/gdrive_client.json (not in git). Google treats the secret of an
installed/TV client as not confidential; it only identifies the app.

No Kodi imports at module level: the core is plain Python so it can be unit-tested with a fake transport.
"""
import json
import os
import time

SCOPE = 'https://www.googleapis.com/auth/drive.file'
DEVICE_URL = 'https://oauth2.googleapis.com/device/code'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
REVOKE_URL = 'https://oauth2.googleapis.com/revoke'
API = 'https://www.googleapis.com/drive/v3'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'
FOLDER = 'application/vnd.google-apps.folder'
ROOT_NAME = 'BN Stream'
SIMPLE_MAX = 5 * 1024 * 1024          # bigger files use a resumable upload
CHUNK = 8 * 1024 * 1024               # resumable chunk (multiple of 256 KiB)


class DriveError(Exception):
    pass


class NotSignedIn(DriveError):
    pass


def _requests():
    import requests
    return requests


class Drive(object):
    """one signed-in Drive. token_path: where the tokens are kept; http: a requests-like module (tests pass a fake)"""

    def __init__(self, client_id, client_secret, token_path, http=None, clock=time.time):
        self.cid, self.secret, self.token_path = client_id, client_secret, token_path
        self.http = http or _requests()
        self.clock = clock
        self._folders = {}

    # ------------------------------------------------------------ tokens
    def _load(self):
        try:
            with open(self.token_path, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self, tok):
        tmp = self.token_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(tok, f)
        os.replace(tmp, self.token_path)

    def signed_in(self):
        return bool(self._load().get('refresh_token'))

    def account(self):
        return self._load().get('email', '')

    def start_login(self):
        """step 1: {'user_code', 'verification_url', 'device_code', 'interval', 'expires_in'}"""
        if not self.cid:
            raise DriveError('no OAuth client configured (gd_client_id)')
        r = self.http.post(DEVICE_URL, data={'client_id': self.cid, 'scope': SCOPE + ' openid email'}, timeout=15)
        d = r.json()
        if r.status_code != 200 or 'device_code' not in d:
            raise DriveError('device code: %s' % (d.get('error_description') or d.get('error') or r.status_code))
        d.setdefault('verification_url', d.get('verification_uri', 'https://www.google.com/device'))
        d.setdefault('interval', 5)
        return d

    def poll_login(self, device_code):
        """step 2 (call every `interval` s): True = signed in, False = still waiting; raises when refused/expired"""
        r = self.http.post(TOKEN_URL, data={'client_id': self.cid, 'client_secret': self.secret, 'device_code': device_code,
                                            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'}, timeout=15)
        d = r.json()
        if 'access_token' in d:
            tok = {'access_token': d['access_token'], 'refresh_token': d.get('refresh_token', ''),
                   'expires': self.clock() + int(d.get('expires_in', 3600)) - 60}
            tok['email'] = self._email(d)
            self._save(tok)
            return True
        err = d.get('error')
        if err in ('authorization_pending', 'slow_down'):
            return False
        raise DriveError(d.get('error_description') or err or 'sign-in failed')

    @staticmethod
    def _email(d):
        """the account name from the id_token (no extra request); '' when absent"""
        try:
            import base64
            part = d['id_token'].split('.')[1]
            return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4))).get('email', '')
        except Exception:
            return ''

    def _access(self):
        tok = self._load()
        if not tok.get('refresh_token'):
            raise NotSignedIn('not signed in to Google Drive')
        if tok.get('access_token') and tok.get('expires', 0) > self.clock():
            return tok['access_token']
        r = self.http.post(TOKEN_URL, data={'client_id': self.cid, 'client_secret': self.secret,
                                            'refresh_token': tok['refresh_token'], 'grant_type': 'refresh_token'}, timeout=15)
        d = r.json()
        if 'access_token' not in d:
            if d.get('error') == 'invalid_grant':            # revoked in the Google account: sign in again
                self._save({})
                raise NotSignedIn('Google sign-in expired or was revoked')
            raise DriveError(d.get('error_description') or d.get('error') or 'token refresh failed')
        tok.update(access_token=d['access_token'], expires=self.clock() + int(d.get('expires_in', 3600)) - 60)
        self._save(tok)
        return tok['access_token']

    def logout(self):
        tok = self._load()
        try:
            if tok.get('refresh_token'):
                self.http.post(REVOKE_URL, data={'token': tok['refresh_token']}, timeout=10)
        except Exception:
            pass
        self._save({})
        self._folders = {}

    # ------------------------------------------------------------ API
    def _call(self, method, url, retry=True, headers=None, timeout=60, **kw):
        hdrs = dict(headers or {}, Authorization='Bearer ' + self._access())
        r = getattr(self.http, method)(url, headers=hdrs, timeout=timeout, **kw)
        if r.status_code == 401 and retry:                   # token revoked/expired early: refresh once
            tok = self._load()
            tok['expires'] = 0
            self._save(tok)
            return self._call(method, url, retry=False, headers=headers, timeout=timeout, **kw)
        if r.status_code >= 400:
            try:
                msg = r.json().get('error', {}).get('message', '')
            except Exception:
                msg = ''
            raise DriveError('%s %s' % (r.status_code, msg or url))
        return r

    def list(self, parent, name=None, folders_only=False):
        q = ["'%s' in parents" % parent, 'trashed=false']
        if name is not None:
            q.append("name='%s'" % name.replace('\\', '\\\\').replace("'", "\\'"))
        if folders_only:
            q.append("mimeType='%s'" % FOLDER)
        out, token = [], None
        while True:
            params = {'q': ' and '.join(q), 'fields': 'nextPageToken,files(id,name,mimeType,size,modifiedTime)',
                      'pageSize': 1000, 'orderBy': 'modifiedTime desc'}
            if token:
                params['pageToken'] = token
            d = self._call('get', API + '/files', params=params).json()
            out += d.get('files', [])
            token = d.get('nextPageToken')
            if not token:
                return out

    def folder(self, *path):
        """id of BN Stream[/path...], created when missing (cached)"""
        key, parent = (), 'root'
        for name in (ROOT_NAME,) + path:
            key += (name,)
            if key not in self._folders:
                found = self.list(parent, name=name, folders_only=True)
                if found:
                    self._folders[key] = found[0]['id']
                else:
                    meta = {'name': name, 'mimeType': FOLDER, 'parents': [parent]}
                    self._folders[key] = self._call('post', API + '/files', json=meta, params={'fields': 'id'}).json()['id']
            parent = self._folders[key]
        return parent

    def upload(self, local, parent, name=None, mime='application/octet-stream', replace=False):
        """upload a file; replace=True overwrites a file of the same name in that folder. returns the file id"""
        name = name or os.path.basename(local)
        old = self.list(parent, name=name) if replace else []
        size = os.path.getsize(local)
        if old:
            meta, method, url = {'name': name}, 'patch', UPLOAD + '/' + old[0]['id']
        else:
            meta, method, url = {'name': name, 'parents': [parent]}, 'post', UPLOAD
        if size <= SIMPLE_MAX:
            boundary = 'bn%d' % int(self.clock() * 1000)
            with open(local, 'rb') as f:
                body = (('--%s\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n%s\r\n--%s\r\nContent-Type: %s\r\n\r\n'
                         % (boundary, json.dumps(meta), boundary, mime)).encode('utf-8') + f.read() +
                        ('\r\n--%s--' % boundary).encode('ascii'))
            r = self._call(method, url, params={'uploadType': 'multipart', 'fields': 'id'}, data=body,
                           headers={'Content-Type': 'multipart/related; boundary=' + boundary})
            return r.json()['id']
        r = self._call(method, url, params={'uploadType': 'resumable', 'fields': 'id'}, json=meta,
                       headers={'X-Upload-Content-Type': mime, 'X-Upload-Content-Length': str(size)})
        session = r.headers['Location']
        with open(local, 'rb') as f:
            pos = 0
            while True:
                chunk = f.read(CHUNK)
                end = pos + len(chunk) - 1
                r = self.http.put(session, data=chunk, timeout=300,
                                  headers={'Content-Range': 'bytes %d-%d/%d' % (pos, end, size)})
                if r.status_code in (200, 201):
                    return r.json()['id']
                if r.status_code != 308:
                    raise DriveError('upload %s: %s' % (name, r.status_code))
                pos = end + 1

    def download(self, file_id, local):
        tmp = local + '.part'
        r = self._call('get', API + '/files/' + file_id, params={'alt': 'media'}, stream=True, timeout=300)
        with open(tmp, 'wb') as f:
            for block in r.iter_content(1 << 16):
                f.write(block)
        os.replace(tmp, local)
        return local

    def delete(self, file_id):
        self._call('delete', API + '/files/' + file_id)

    def usage(self):
        """(used bytes, limit bytes or 0 for unlimited)"""
        q = self._call('get', API + '/about', params={'fields': 'storageQuota'}).json().get('storageQuota', {})
        return int(q.get('usage', 0)), int(q.get('limit', 0) or 0)


# ------------------------------------------------------------ merge (sync between devices), pure
def _ts(v):
    """sortable key of NovaTV's 'dd/mm/YYYY HH:MM' (common.now_str) or an ISO time; '' sorts first"""
    import re
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})', v or '')
    if m:
        d, mo, y, h, mi = m.groups()
        return '%s-%s-%sT%s:%s' % (y, mo, d, h, mi)
    return v or ''


def merge_favourites(local, remote, removed_local=(), removed_remote=()):
    """union by (kind, id); an item removed on any device after it was added stays removed. newest first"""
    gone = {}
    for r in list(removed_local) + list(removed_remote):
        k = (r.get('kind'), str(r.get('id')))
        gone[k] = max(gone.get(k, ''), _ts(r.get('removed', '')))
    out, seen = [], set()
    for f in list(local) + list(remote):
        k = (f.get('kind'), str(f.get('id')))
        if k in seen or (k in gone and gone[k] >= _ts(f.get('added', ''))):
            continue
        seen.add(k)
        out.append(f)
    return sorted(out, key=lambda f: _ts(f.get('added', '')), reverse=True)


def merge_history(local, remote, limit=2000):
    """union by key, the latest watch wins. newest first"""
    best = {}
    for h in list(local) + list(remote):
        k = h.get('key')
        if k and (k not in best or _ts(h.get('when', '')) > _ts(best[k].get('when', ''))):
            best[k] = h
    return sorted(best.values(), key=lambda h: _ts(h.get('when', '')), reverse=True)[:limit]


def merge_removed(a, b):
    """tombstones of removed favourites from both devices (latest per item)"""
    best = {}
    for r in list(a) + list(b):
        k = (r.get('kind'), str(r.get('id')))
        if k not in best or _ts(r.get('removed', '')) > _ts(best[k].get('removed', '')):
            best[k] = r
    return sorted(best.values(), key=lambda r: _ts(r.get('removed', '')), reverse=True)[:1000]


def prune(files, keep):
    """backups to delete: all but the newest `keep` (files as returned by list(): newest first)"""
    backups = [f for f in files if f.get('name', '').endswith('.zip')]
    return backups[keep:]

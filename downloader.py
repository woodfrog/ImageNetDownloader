import os
from urllib.parse import urlsplit
import json
from concurrent import futures
import tarfile

import requests


def save_info(username, accesskey):
    userinfo_filename = 'userInfo.json'

    data = {
        'username': username,
        'accesskey': accesskey
    }

    with open(userinfo_filename, 'w') as fp:
        json.dump(data, fp, sort_keys=True, indent=4, ensure_ascii=False)


def read_info():
    filename = 'userInfo.json'
    if not os.path.exists(filename):
        return None

    with open(filename, 'r') as f:
        data = json.load(f)

    try:
        return data['username'], data['accesskey']
    except Exception:
        return None


class Downloader:
    def __init__(self):
        self.max_workers = 10
        self.username = None
        self.accessKey = None

    def download_file(self, url, *, saved_path=None, filename=None):
        if filename is None:
            # url : <scheme>://<netloc>/<path>?<query>#<fragment>
            scheme, netloc, path, query, fragment = urlsplit(url)
            filename = os.path.basename(path)

        if saved_path:
            filename = os.path.join(saved_path, filename)

        r = requests.get(url, stream=True)  # make stream True to save memory space

        try:
            total_size = r.headers['Content-Length']
            print('Downloading from: {} Size(Bytes): {}'.format(url, total_size))
        except KeyError:
            print('Cannot find size information')

        with open(filename, 'wb') as fp:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    fp.write(chunk)

        return filename

    def mkdir_wnid(self, wnid):
        if not os.path.exists(wnid):
            os.mkdir(wnid)
        return os.path.abspath(wnid)

    def extract_tar(self, filename):
        tar = tarfile.open(filename)
        tar.extractall()
        tar.close()

    def download_original_image(self, wnid):
        download_url = 'http://www.image-net.org/download/synset?wnid={}&username={}&accesskey={}&release=latest&src=stanford'.format(
            wnid, self.username, self.accessKey)

        try:
            download_file = self.download_file(download_url, saved_path=self.mkdir_wnid(wnid), filename=(wnid + '.tar'))
        except:
            print('fail to download file from {}'.format(download_url))

        base_dir = os.getcwd()
        os.chdir(wnid)
        # extract the tar file and then remove it
        self.extract_tar(download_file)
        os.remove(download_file)
        os.chdir(base_dir)
        return wnid

    def get_hyponym_list(self, wnid):
        url = 'http://www.image-net.org/api/text/wordnet.structure.hyponym?wnid={}&full=1'.format(wnid)
        r = requests.get(url)
        wnid_list = r.text.split('\r\n')
        hyponym_list = list()
        for wnid in wnid_list[1:]:
            if wnid != '':
                hyponym_list.append(wnid[1:])
        return hyponym_list

    def download_synset(self, wnid):
        info = read_info()
        if info is not None:
            self.username, self.accessKey = info

        if self.username is None or self.accessKey is None:
            self.username = input('Enter your username : ')
            self.accessKey = input('Enter your accessKey : ')
            if self.username and self.accessKey:
                save_info(self.username, self.accessKey)

        wnid_list = self.get_hyponym_list(wnid)

        workers = min(self.max_workers, len(wnid_list))
        with futures.ThreadPoolExecutor(workers) as executor:
            tasks = list()
            for wnid in wnid_list:
                future = executor.submit(self.download_original_image, wnid)
                tasks.append(future)
                print('{} scheduled'.format(wnid))

            for future in futures.as_completed(tasks):
                res = future.result()
                print('{} has been downloaded'.format(wnid))


if __name__ == '__main__':
    downloader = Downloader()
    downloader.download_synset('n07707451')

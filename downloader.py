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

    @staticmethod
    def _download_file(url, saved_path=None, filename=None):
        if filename is None:
            # url : <scheme>://<netloc>/<path>?<query>#<fragment>
            scheme, netloc, path, query, fragment = urlsplit(url)
            filename = os.path.basename(path)

        if saved_path:
            filename = os.path.join(saved_path, filename)

        r = requests.get(url, stream=True, timeout=10)  # make stream True to save memory space

        try:
            total_size = r.headers['Content-Length']
            print('Downloading from: {} Size(Bytes): {}'.format(url, total_size))
        except KeyError:
            print('Cannot find size information for {}'.format(url))

        with open(filename, 'wb') as fp:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    fp.write(chunk)

        return filename

    @staticmethod
    def mkdir_wnid(wnid):
        if not os.path.exists(wnid):
            os.mkdir(wnid)
        return os.path.abspath(wnid)

    @staticmethod
    def extract_tar(filename):
        tar = tarfile.open(filename)
        tar.extractall()
        tar.close()

    def download_original_image(self, wnid):
        download_url = 'http://www.image-net.org/download/synset?wnid={}&username={}&accesskey={}&release=latest&src=stanford'.format(
            wnid, self.username, self.accessKey)

        wnid_path = self.mkdir_wnid(wnid)
        try:
            download_file = self._download_file(download_url, saved_path=wnid_path, filename=(wnid + '.tar'))
        except requests.exceptions.Timeout:
            print('fail to download file from {} for {}'.format(download_url, wnid))
            os.rmdir(wnid_path)
            return None

        base_dir = os.getcwd()
        os.chdir(wnid)
        # extract the tar file and then remove it
        self.extract_tar(download_file)
        os.remove(download_file)
        os.chdir(base_dir)
        return wnid

    def download_synsets(self, wnid_list):
        '''
        Given a list of wnid, download the images for the corresponding synsets
        :param wnid_list: the wnids for all synsets that need to be downloaded
        '''
        # get user info
        info = read_info()
        if info is not None:
            self.username, self.accessKey = info

        if self.username is None or self.accessKey is None:
            self.username = input('Enter your username : ')
            self.accessKey = input('Enter your accessKey : ')
            if self.username and self.accessKey:
                save_info(self.username, self.accessKey)

        workers = min(self.max_workers, len(wnid_list))
        with futures.ThreadPoolExecutor(workers) as executor:
            tasks = list()
            for wnid in wnid_list:
                future = executor.submit(self.download_original_image, wnid)
                tasks.append(future)
                print('{} scheduled'.format(wnid))

            for future in futures.as_completed(tasks):
                res = future.result()
                if res:
                    print('{} has been downloaded'.format(res))

    @staticmethod
    def _get_hyponym_list(wnid):
        url = 'http://www.image-net.org/api/text/wordnet.structure.hyponym?wnid={}&full=1'.format(wnid)
        r = requests.get(url, timeout=5)
        wnid_list = r.text.split('\r\n')
        hyponym_list = list()
        for wnid in wnid_list[1:]:
            if wnid != '':
                hyponym_list.append(wnid[1:])
        return hyponym_list

    def download_all_hyponym(self, wnid):
        '''
        Given a wnid of a synset, download all the hyponyms for this synset.
        :param wnid: the wnid of the parent synset
        '''
        try:
            hyponym_list = self._get_hyponym_list(wnid)
        except requests.exceptions.Timeout:
            print('Time Out when trying to get hyponym list for wnid{}. Check connection'.format(wnid))
            return

        self.download_synsets(hyponym_list)


if __name__ == '__main__':
    downloader = Downloader()
    downloader.download_all_hyponym('n07707451')

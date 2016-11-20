import os
from urllib.parse import urlsplit
import json
from concurrent import futures
import tarfile
import shutil

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
    def __init__(self, main_path=None):
        self.max_workers = 5
        self.username = None
        self.accessKey = None
        self.success_count = 0
        self.failure_count = 0
        self.main_path = main_path
        if self.main_path:
            os.chdir(self.main_path)

    @staticmethod
    def _download_file(url, saved_path=None, filename=None):
        if filename is None:
            # url : <scheme>://<netloc>/<path>?<query>#<fragment>
            scheme, netloc, path, query, fragment = urlsplit(url)
            filename = os.path.basename(path)

        if saved_path:
            filename = os.path.join(saved_path, filename)

        r = requests.get(url, stream=True, timeout=100)  # make stream True to save memory space

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
    def mkdir_synset(wnid):
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

        # get the corresponding name for the specified wnid
        try:
            wnid_name = self._get_wnid_text(wnid)
        except (requests.exceptions.Timeout, TimeoutError):
            print('Timeout when trying to get the name for {}'.format(wnid))
            return None

        wnid_path = self.mkdir_synset(wnid_name)
        try:
            download_file = self._download_file(download_url, saved_path=wnid_path, filename=(wnid + '.tar'))
        except (requests.exceptions.Timeout, TimeoutError):
            print('fail to download file from {} for {}'.format(download_url, wnid))
            shutil.rmtree(wnid_path)
            return None

        base_dir = os.getcwd()
        os.chdir(wnid_name)
        # extract the tar file and then remove it
        try:
            self.extract_tar(download_file)
        except tarfile.ReadError:
            os.chdir(base_dir)
            print('fail to open {}, return to the original path'.format(download_file))
            return None

        os.remove(download_file)
        os.chdir(base_dir)
        return wnid_name

    def download_synsets(self, wnid_list):
        '''
        Given a list of wnid, download the images for the corresponding synsets
        :param wnid_list: the wnids for all synsets that need to be downloaded
        '''
        self.failure_count = 0
        self.success_count = 0

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
                    self.success_count += 1
                    print('{} has been downloaded'.format(res))
                else:  # res is None, this task failed
                    self.failure_count += 1

            print('Misson Completed. {} success, {} failure'.format(self.success_count, self.failure_count))

    @staticmethod
    def _get_hyponym_list(wnid):
        url = 'http://www.image-net.org/api/text/wordnet.structure.hyponym?wnid={}'.format(wnid)
        r = requests.get(url, timeout=50)
        wnid_list = r.text.split('\r\n')
        hyponym_list = list()
        for wnid in wnid_list[1:]:
            if wnid != '':
                hyponym_list.append(wnid[1:])
        return hyponym_list

    @staticmethod
    def _get_wnid_text(wnid):
        url = 'http://www.image-net.org/api/text/wordnet.synset.getwords?wnid={}'.format(wnid)
        r = requests.get(url, timeout=100)
        words = r.text.split('\n')
        result = 'n_' + '_'.join(words)
        return result[:-1]

    def download_first_level_hyponym(self, wnid):
        '''
        Given a wnid of a synset, download all the hyponyms for this synset.
        :param wnid: the wnid of the parent synset
        '''
        try:
            hyponym_list = self._get_hyponym_list(wnid)
        except (requests.exceptions.Timeout, TimeoutError):
            print('Time Out when trying to get hyponym list for wnid {}. Check connection'.format(wnid))
            return

        self.download_synsets(hyponym_list)


if __name__ == '__main__':
    downloader = Downloader()
    downloader.download_first_level_hyponym('n07705931')

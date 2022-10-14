from ftplib import FTP
import re
import os
from collections import namedtuple, defaultdict
import datetime
from datetime import timedelta
import logging
MONTH_MAPPING = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep' ,'Oct', 'Nov' ,'Dec']
TIME_MATCHING = re.compile(r'\d\d:\d\d ')


class Hw_downloader(object):
    def __init__(self):
        self.ip = "140.116.154.1"
        self.port = 2121
        self.hw_file = namedtuple('Hw_file', ['timestamp', 'file_name', 'name','version'] ) # S_ID = student id
        self.ftp = None
    def connect(self, username:str, password:str):
        self.ftp = FTP()
        self.ftp.connect(self.ip, int(self.port))

        try:
            self.ftp.login(username, password)
            self.ftp.encoding = 'big5'
            print("Login successful")
            return 1
        except:
            print("Login failed")
            return 0

    def list_folders(self, path):
        # Search ftp
        search_result = []
        self.ftp.dir(path, search_result.append)
        folders = []
        for f in search_result:
            info = f.split()[5:]

            file_name = info[3]
            # Skip
            if file_name == '.' or file_name == '..':
                continue
            folders.append(file_name)
        return folders

    def list_hw_files(self, path:str):

        # Search ftp
        search_result = []
        self.ftp.dir(path, search_result.append)
        # Process files
        files = defaultdict(list)
        error_files = []
        success_count = 0
        error_for_space = 0
        error_for_format = 0 
        for f in search_result:
            info = f.split()[5:]
            # file name contain space
            # if len(info) > 4:
            #     error_for_space += 1
            #     error_files.append(" ".join(info[3:]))
            #     continue

            # Timestamp
            month = MONTH_MAPPING.index(info[0]) + 1
            day = int(info[1])
            hour = int(info[2].split(':')[0])
            min = int(info[2].split(':')[1])
            timestamp = datetime.datetime(2022, month, day, hour, min)
            # Ftp server use + 0, and we use + 8
            timestamp = timestamp + timedelta(hours=8)
            if len(info) > 4:
                match = TIME_MATCHING.search(f)
                file_name = f[match.span(0)[1]:]
            else:
                file_name = info[3]
            
            # Skip
            if file_name == '.' or file_name == '..':
                continue
            # Extension Errror
            if file_name[-4:].lower() != ".zip" and file_name[-4:].lower() != ".rar":
                error_for_format += 1
                error_files.append(file_name)
                continue
            
            info = file_name.split('_')

            version = info[-1].split('.')[0]
            # Version Flag exists
            if "v" in version.lower() or version.lower().isdigit():
                if version.lower().isdigit():
                    version = int(version)
                else:
                    version = int(version[1:])
                 # name
                name = info[-2]
                # S_ID
                student_id = info[-3].upper()
                file = self.hw_file(timestamp, file_name, name, version)
                files[student_id].append(file)
            # No version Flag
            else:
                name = version
                version = 0
                student_id = info[-2].upper()

            file = self.hw_file(timestamp, file_name, name, version)
            files[student_id].append(file)
            success_count += 1
               
        error_count = error_for_space + error_for_format
        return files, success_count, error_count, error_files
    def download_file(self, path: str, output_path: str):
        # self.ftp.cwd(os.path.dirname(path))
        # print(self.ftp.pwd())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        f = open(output_path, "wb")
        if "F74096247" in path:
            print(path)
        download_cmd = 'RETR %s' % (path)
        self.ftp.retrbinary(download_cmd, f.write)
        f.close()
        

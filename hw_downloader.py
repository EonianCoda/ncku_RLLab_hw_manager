from ftplib import FTP
import re
import os
from collections import namedtuple, defaultdict
import datetime
from datetime import timedelta
# MONTH_MAPPING = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep' ,'Oct', 'Nov' ,'Dec']
# TIME_MATCHING = re.compile(r'\d\d:\d\d ')


class Hw_downloader(object):
    def __init__(self, courses : list,
                        course_stduent_list : list):
        """This is a class for manage ftp
        Attributes:
            course: a list of string, which contains courses
            course_student_list: a lish of path, which contains csv files
        """

        self.ip = "140.116.154.1"
        self.port = 2121
        self.hw_file = namedtuple('Hw_file', ['timestamp', 'file_name', 'name','version','size'] ) # S_ID = student id
        self.ftp = None


        if len(courses) != len(course_stduent_list) or courses == 0:
            raise ValueError("Length of course or course_stdudent_list have some error!")

        self.student_IDS = defaultdict(list)
        self.student_names = defaultdict(list)
        for course, csv_file in zip(courses, course_stduent_list):
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines[1:]:
                line = line.replace("\u3000",'').replace("\n",'')
                name = line.split(',')[0]
                stdID = line.split(',')[1].lower()
                self.student_names[course].append(name)
                self.student_IDS[course].append(stdID)

    def connect(self, username:str, password:str):
        self.ftp = FTP()
        self.ftp.connect(self.ip, int(self.port))
        try:
            self.ftp.login(username, password)
            self.username = username
            self.password = password
            self.ftp.encoding = 'utf-8'
            print("Login successful")
            return 1
        except:
            print("Login failed")
            return 0
    def reconnect(self):
        self.ftp.connect(self.ip, int(self.port))
        self.ftp.login(self.username, self.password)
        print("Reconnect")
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
    
    def list_hw_files(self, path:str, course:str):
        # Process files
        error_files = []
        version_matcher = re.compile(u'[vV]+[\d][\d]?[\s]*.')
        chinese_name_matcher = re.compile(u'[\u4e00-\u9fa5]+')
        good_files = defaultdict(list)
        success_count = 0
        # List files
        files = [f for f in self.ftp.mlsd(path=path,facts=["Modify","Type","Size"])]
        for i, f in enumerate(files):
            if f[1]['type'] != "file":
                continue

            # TimeStamp
            modified_time = f[1]['modify']
            year = int(modified_time[0:4])
            month = int(modified_time[4:6])
            day = int(modified_time[6:8])
            hour = int(modified_time[8:10])
            min = int(modified_time[10:12])
            timestamp = datetime.datetime(year, month, day, hour, min)
            # Ftp server use + 0, and we use + 8
            timestamp = timestamp + timedelta(hours=8)

            # File Size
            file_size = float(f[1]['size']) / (1024 * 1024) # MB
            file_size = "{:.3f}".format(file_size)            

            # FileName
            file_name = f[0].lower()

            # The name of files on Windows cannot contain question mark(?)
            if '?' in file_name:
                error_files.append((file_name,"檔名中包含?"))
                continue
            # Extension Error
            if file_name[-4:].lower() != ".zip" and file_name[-4:].lower() != ".rar" and file_name[-4:].lower() != ".tar" and file_name[-3:].lower() != ".7z":
                error_files.append((file_name,"副檔名錯誤"))
                continue

            # Find Version
            match = version_matcher.search(file_name)
            if match == None: # No version
                version = 0
            else:
                version = int(match.group()[:-1].strip()[1:])
            # Find student ID
            student_id = None
            for s_id in self.student_IDS[course]:
                matcher = re.compile(s_id)
                match = matcher.search(file_name)
                if match != None:
                    student_id = s_id
                    break

            # Find Chinese Name
            chinese_name = chinese_name_matcher.search(file_name)
            if chinese_name == None:
                chinese_name = ""
            else:
                chinese_name = chinese_name.group()
            
            # No student ID and chinese name
            if student_id == None and chinese_name == "":
                error_files.append((file_name,"學號不存在or學號不在學生名單中 and 姓名不存在"))
                continue
            elif student_id == None:
                if chinese_name in self.student_names[course]:
                    # Get student id from chinese name
                    idx = self.student_names[course].index(chinese_name)
                    # Duplicate name exist
                    if chinese_name in self.student_names[course][idx + 1:]:
                        error_files.append((file_name,"學號不存在，並且姓名可能存在重複"))
                        continue
                    student_id = self.student_IDS[course][idx]
                # Cannot match chinese name
                else:
                    error_files.append((file_name,"學號不存在，並且姓名對不回去學號"))
                    continue
            elif chinese_name == "":
                idx = self.student_IDS[course].index(student_id)
                chinese_name = self.student_names[course][idx]

            good_files[student_id].append({'timestamp': timestamp,
                                            'file_name': f[0],
                                            'chinese_name': chinese_name,
                                            'version': version,
                                            'file_size': file_size})
            success_count += 1
        return good_files, success_count, len(error_files), error_files
    def download_file(self, path: str, output_path: str):

        self.ftp.encoding = 'big5'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        f = open(output_path, "wb")
        download_cmd = 'RETR %s' % (path)
        self.ftp.retrbinary(download_cmd, f.write)
        f.close()
        self.ftp.encoding = 'utf-8'
        


from os.path import isdir
import shutil
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from UI import Ui_Form
from hw_downloader import Hw_downloader
from collections import defaultdict
import os
import patoolib # for rar file
import pickle
import ftplib
from pathlib import Path
import subprocess
FOLDER_PATH = "/Course/{}/Upload/Homework/"
COURSE_FOLDERS = ['CvDl_2022_G', 'OpenCvDl_2022_Bs']
COURSE_STUDENT_LIST = ['cvdl_students.csv', 'opencvdl_students.csv']

LOGIN_INFO = "login.key"
DOWNLOAD_FILE_ROOT = Path("./download")

##################### For Debug #########################
# if os.path.isdir(DOWNLOAD_FILE_ROOT):
#     shutil.rmtree(DOWNLOAD_FILE_ROOT)

##TODO 統整Error => 等待check
##TODO 刪除解壓縮失敗的資料夾 => 等待check
##TODO 遲交分數比例

##TODO GIF圖檔失真
##TODO 匯出後打開資料夾變為打開excel

login_success_styleSheet = """
QLabel
{	
	font: 75 20pt "微軟正黑體";
	font-weight:bold;
	color: green;
}
"""
def unzip(file_path : str, output_directory : str):
    os.makedirs(output_directory, exist_ok=True)
    output_directory = str(output_directory)
    file_path = str(file_path)
    patoolib.extract_archive(file_path, outdir=output_directory)


class LoadingProgress(QtWidgets.QDialog):
    update_title_signal = pyqtSignal(str)
    update_content_signal = pyqtSignal(str)
    finished = pyqtSignal()
    def __init__(self, parent):
        super(LoadingProgress, self).__init__(parent)
        # self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint ^ QtCore.Qt.WindowCloseButtonHint)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("訊息")
        self.value = 0
        vbox = QtWidgets.QVBoxLayout(self)
        # Set gif movie
        self.movie_label = QtWidgets.QLabel()
        self.movie = QtGui.QMovie("./UI_imgs/loading.gif")
        self.movie_label.setMovie(self.movie)
        self.movie_label.setScaledContents(True)
        self.movie.start()
        self.progress_label = QtWidgets.QLabel()

        vbox.addWidget(self.movie_label)
        vbox.addWidget(self.progress_label)
        
        self.setLayout(vbox)
        self.setStyleSheet("background-color:white;")

        self.setup_signal()
    def setup_signal(self):
        self.finished.connect(self.close_progress)
        self.update_title_signal.connect(self.update_title)
        self.update_content_signal.connect(self.update_content)
    def close_progress(self):
        self.close()
    def update_title(self, title:str):
        self.setWindowTitle(title)
    def update_content(self, content:str):
        self.progress_label.setText(content)
    # def initialize(self):
    #     self.value = 0
    # def label_update(self):
    #     self.progress_label.setText(self.steps[self.value])
    
    # def update_progress(self) -> None:
    #     self.value += 1
    #     if self.value < len(self.steps):
    #         self.label_update()
    #     else:
    #         self.close()


class Download_files_thread(QThread):
    def __init__(self, loading_bar:LoadingProgress,
                        downloader : Hw_downloader,
                        root_dir : str,
                        ftp_target_path : str,
                        submitted_files : dict,
                        hw_mark : str,
                        ):
        super().__init__()
        self.loading_bar = loading_bar

        self.downloader = downloader
        self.root_dir = root_dir
        self.ftp_target_path = ftp_target_path
        self.submitted_files = submitted_files
        self.hw_mark = hw_mark

    def run(self):
        self.loading_bar.update_title_signal.emit("下載檔案中")

        download_files_path = []
        

        error_lines = ['錯誤檔案名稱, 錯誤類別, 錯誤訊息\n']
        # download_error_lines = ['錯誤檔案名稱, 錯誤訊息\n']
        reconnect_times = 0
        remove_list = []
        # Download Files
        for idx, (s_id, datas) in enumerate(self.submitted_files.items()):
            max_timestamp = datas[0][0]
            max_idx = 0
            for i, data in enumerate(datas[1:]):
                if data[0] > max_timestamp:
                    max_timestamp = data[0]
                    max_idx = i
            data = datas[max_idx]
            file_name = data[1]

            ftp_path = "{}/{}".format(self.ftp_target_path, file_name)
            output_path = os.path.join(self.root_dir, file_name)
            

            self.loading_bar.update_content_signal.emit("正在下載({}/{}) {}".format(idx, len(self.submitted_files),file_name))
            try:
                self.downloader.download_file(ftp_path, output_path)
                reconnect_times = 0
                download_files_path.append(output_path)
            # No such file
            except ftplib.error_perm as e:
                error_lines.append("{},{},{}\n".format(file_name, "download", e.__str__().replace(",","，")))
                remove_list.append(output_path)
            except UnicodeEncodeError as e:
                error_lines.append("{},{},{}\n".format(file_name, "download", e.__str__().replace(",","，")))
                remove_list.append(output_path)
            # Server or Out Pc error
            except ftplib.error_temp as e:
                if reconnect_times == 1:
                    print(e)
                    raise SystemError("Some Fatal error")
                reconnect_times += 1
                self.downloader.reconnect()
                error_lines.append("{},{},{}\n".format(file_name, "download", "Exception ftplib.error_temp"))
            except ConnectionAbortedError as e:
                if reconnect_times == 1:
                    print(e)
                    raise SystemError("Some Fatal error")
                reconnect_times += 1
                self.downloader.reconnect()
                error_lines.append("{},{},{}\n".format(file_name, "download", "ConnectionAbortedError"))
        # with open(self.root_dir / ".." / "{}_download_error.csv".format(self.hw_mark), 'w', encoding='utf-8') as f:
        #     f.write('\ufeff')
        #     f.writelines(download_error_lines)

        # Remove File which failed to download
        for f in remove_list:
            os.remove(f)
        # download_files_path = os.listdir(self.root_dir)
        # download_files_path = [self.root_dir / f for f in download_files_path]
        remove_list = []
        self.loading_bar.update_title_signal.emit("解壓縮檔案中")
        #error_zip_lines = ['錯誤檔案名稱, 錯誤訊息']
        # # Unzip files
        for idx, file in enumerate(download_files_path):
            out_directory = os.path.basename(file)
            if ".7z" in out_directory:
                out_directory = out_directory[:-3]
            else:
                out_directory = out_directory[:-4]
            output_path = self.root_dir / out_directory
            
            self.loading_bar.update_content_signal.emit("正在解壓縮({}/{}) {}".format(idx, len(download_files_path),os.path.basename(file)))
            try:
                unzip(file, output_path)
                os.remove(file)
            # unzip error
            except Exception as e:
                remove_list.append(output_path)
                error_lines.append("{},{},{}\n".format(os.path.basename(file), "unzip", e.__str__().replace(",","，")))
        # Remove directory which failed to unzip
        for f in remove_list:
            shutil.rmtree(f)

        # Write Error messages
        #lines = [f + '\n' for f in error_zip_lines]
        with open(self.root_dir / ".." / "{}_download_and_unzip_error.csv".format(self.hw_mark), 'w', encoding='utf-8') as f:
            f.write('\ufeff')
            f.writelines(error_lines)

        self.loading_bar.finished.emit()
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.downloader = Hw_downloader(courses=COURSE_FOLDERS, course_stduent_list=COURSE_STUDENT_LIST)

        self.ui.course_selecter.addItems(COURSE_FOLDERS)
        self.ui.course_selecter.currentTextChanged.connect(self.change_hw_options)
        self.submitted_files = None
        self.error_files = None
        self.ftp_target_path = None
        
        self.dlg = QMessageBox(self)
        # For testing
        self.hw_folders = {'CvDl_2022_G':['hw1_1'], 'OpenCvDl_2022_Bs':['hw1_1', 'hw_1_2']}
        self.ui.hw_selecter.addItems(['hw1_1', 'hw_1_2'])
        
        if os.path.isfile(LOGIN_INFO):
            with open("login.key", 'rb') as f:
                username, password = pickle.load(f)
            self.ui.username.setText(username)
            self.ui.password.setText(password)
        self.setup_control()
        self.loading_bar = LoadingProgress(self)
        
        self.download_thread = None
    def check_login(self) -> bool:
        """Check whether ftp object exists
        """
        if self.downloader.ftp == None:
            self.show_not_connect_message()
            return False
        return True
    
    def setup_control(self):
        self.ui.login_btn.clicked.connect(self.login_ftp)
        self.ui.search_files_btn.clicked.connect(self.search_files)
        self.ui.download_hw_btn.clicked.connect(self.download_files)
        self.ui.output_submitted_info_btn.clicked.connect(self.output_submitted_info)
        self.ui.set_delay_time.clicked.connect(self.set_delay_time)
        self.ui.login_and_store_btn.clicked.connect(self.login_and_store)

        self.ui.hw_selecter.currentTextChanged.connect(self.set_search_path)
        self.ui.course_selecter.currentTextChanged.connect(self.set_search_path)
    
    def login_ftp(self):
        # username or password is empty
        if self.ui.username.text() == "" or self.ui.password.text() == "":
            self.dlg.setWindowTitle("警告")
            self.dlg.setText("帳號或密碼不得為空")
            self.dlg.exec()
            return False
        success = self.downloader.connect(self.ui.username.text(), self.ui.password.text())
        
        # Fail login
        if not success:
            self.dlg.setWindowTitle("登入失敗")
            self.dlg.setText("請重新登入")
            self.dlg.exec()
            return False

        self.search_folders()
        self.dlg.setWindowTitle("登入成功")
        self.dlg.setText("歡迎使用")
        self.dlg.exec()
        self.ui.login_status_label.setStyleSheet(login_success_styleSheet) 
        self.ui.login_status_label.setText("登入狀態: 已登入")

        return True
    def login_and_store(self):
        success = self.login_ftp()
        # Store password
        if success:
            username = self.ui.username.text()
            password = self.ui.password.text()
            with open("login.key", 'wb') as f:
                pickle.dump((username, password), f)


    def set_delay_time(self):
        date = self.ui.set_date.selectedDate()
        time = self.ui.set_time.time()
        self.ui.delay_time_show.setDate(date)
        self.ui.delay_time_show.setTime(time)

        # print(self.ui.delay_time_show.dateTime().toPyDateTime())
    def output_submitted_info(self):
        if not self.check_login() or self.submitted_files == None:
            return
        
        contents = ["學號,姓名,最終版本,檔案名稱,最後更新時間,遲交\n"]

        delay_time = self.ui.delay_time_show.dateTime().toPyDateTime()

        for s_id, datas in self.submitted_files.items():
            max_timestamp = datas[0][0]
            max_idx = 0
            for i, data in enumerate(datas[1:]):
                if data[0] > max_timestamp:
                    max_timestamp = data[0]
                    max_idx = i
            data = datas[max_idx]

            if data[0] > delay_time:
                delay = 1
            else:
                delay = 0
            line = "{},{},{},{},{},{}\n".format(s_id.upper(), data[2], data[3], data[1], data[0].strftime("%Y/%m/%d %H:%m"), delay)
            contents.append(line)
        
        csv_file_name = "{}.csv".format(self.cur_hw)
        output_path = DOWNLOAD_FILE_ROOT / self.cur_course_name
        os.makedirs(output_path, exist_ok=True)
        with open(output_path / csv_file_name, 'w', encoding='utf-8') as f:
            f.write('\ufeff')
            f.writelines(contents)

        if len(self.error_files) != 0:
            file_name = "{}_submit_error.csv".format(self.cur_hw)
            lines = [f + '\n' for f in self.error_files]
            with open(output_path / file_name, 'w', encoding='utf-8') as f:
                f.write('\ufeff')
                f.writelines(lines)

        # Open Explorer
        #subprocess.run(['"C:\\Program Files\\Microsoft Office\\root\\Office16\\EXCEL.EXE"',(output_path / csv_file_name)])
       
        #subprocess.run('C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Excel.exe "{}"'.format(output_path / csv_file_name))
        # os.system('C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Excel.exe "{}"'.format(csv_file_name))
        os.system('explorer.exe "{}"'.format(output_path))
    
    def download_files(self):
        if not self.check_login() or self.submitted_files == None:
            return
        if self.download_thread != None and self.download_thread.isFinished() == False:
            self.dlg.setWindowTitle("警告")
            self.dlg.setText("請不要按兩次下載，下載還未完成")
            self.dlg.exec()
            return

        self.loading_bar.show()

        root_dir = DOWNLOAD_FILE_ROOT / self.cur_course_name / self.cur_hw
        os.makedirs(root_dir, exist_ok=True)
        self.download_thread = Download_files_thread(loading_bar=self.loading_bar, 
                                                    downloader=self.downloader,
                                                    root_dir = root_dir,
                                                    ftp_target_path = self.ftp_target_path,
                                                    hw_mark=self.cur_hw,
                                                    submitted_files = self.submitted_files)
        self.download_thread.start()                                   

        # self._file_paths = []
        # root_dir = "./{}/{}/".format(self.cur_course_name, self.cur_hw)
        # error_download_files = ['錯誤檔案名稱, 錯誤訊息']
        # reconnect_times = 0
        # for s_id, datas in self.submitted_files.items():
        #     max_timestamp = datas[0][0]
        #     max_idx = 0
        #     for i, data in enumerate(datas[1:]):
        #         if data[0] > max_timestamp:
        #             max_timestamp = data
        #             max_idx = i
        #     data = datas[max_idx]
        #     file_name = data[1]

        #     ftp_path = "{}/{}".format(self.ftp_target_path, file_name)
        #     output_path = os.path.join(root_dir, file_name)
        #     self._file_paths.append(output_path)

        #     try:
        #         self.downloader.download_file(ftp_path, output_path)
        #         reconnect_times = 0
        #     # No such file
        #     except ftplib.error_perm as e:
        #         error_download_files.append("{},{}".format(file_name, e.__str__().replace(",","，")))
        #     except UnicodeEncodeError as e:
        #         error_download_files.append("{},{}".format(file_name, e.__str__().replace(",","，")))
        #     except ftplib.error_temp as e:
        #         if reconnect_times == 1:
        #             print(e)
        #             raise SystemError("Some Fatal error")
        #         reconnect_times += 1
        #         self.downloader.connect(self.ui.username.text(), self.ui.password.text())
        #     except ConnectionAbortedError as e:
        #         if reconnect_times == 1:
        #             print(e)
        #             raise SystemError("Some Fatal error")
        #         reconnect_times += 1
        #         self.downloader.connect(self.ui.username.text(), self.ui.password.text())
    

        # file_name = "{}_{}_download_error.csv".format(self.cur_course_name, self.cur_hw)
        
        # root_dir = "./{}/{}/".format(self.cur_course_name, self.cur_hw)
        # self.loading_bar.update_signal.emit()
        # error_zip_files = ['錯誤檔案名稱, 錯誤訊息']
        # # Unzip files
        # if self.ui.auto_unzip_ckb.isChecked():
        #     for file in self._file_paths:
        #         out_directory = os.path.basename(file)[:-4]
        #         output_path = os.path.join(root_dir, out_directory)
        #         try:
        #             unzip(file, output_path)
        #             os.remove(file)
        #         # unzip error
        #         except Exception as e:
        #             error_zip_files.append("{},{}".format(os.path.basename(file), e.__str__().replace(",","，")))
        #     lines = [f + '\n' for f in error_zip_files]
        #     with open(file_name, 'w', encoding='big5') as f:
        #         f.writelines(lines)

    def show_not_connect_message(self):
        self.dlg.setWindowTitle("錯誤")
        self.dlg.setText("請先登入後再執行此功能")
        self.dlg.exec()
    def search_files(self):
        if not self.check_login():
            return
        path = self.ui.search_path_show.text()
        self.ftp_target_path = path
        files, success_count, error_count, error_files = self.downloader.list_hw_files(path, self.cur_course_name)

        self.submitted_files = files
        self.error_files = error_files
        self.ui.available_files_label.setText("有效檔案: {}".format(success_count))
        self.ui.unavailable_files_label.setText("無效檔案: {}".format(error_count))
        self.ui.submitted_student_num_label.setText("繳交人數: {}".format(len(self.submitted_files)))

        self.ui.output_submitted_info_btn.setEnabled(True)
        self.ui.download_hw_btn.setEnabled(True)
    def set_search_path(self):
        cur_course = self.cur_course_name
        path = FOLDER_PATH.format(cur_course) + self.cur_hw
        self.ui.search_path_show.setText(path)
        self.ui.search_files_btn.setEnabled(True)

    def change_hw_options(self, value : str):
        self.ui.hw_selecter.clear()
        self.ui.hw_selecter.addItems(self.hw_folders[value])
        
    def search_folders(self):
        if self.downloader.ftp == None:
            self.show_not_connect_message()
            return
        self.hw_folders = defaultdict(list)
        for folder in COURSE_FOLDERS:
            path = FOLDER_PATH.format(folder)
            folders = self.downloader.list_folders(path)
            self.hw_folders[folder] = folders
        # Set current select
        cur_select = self.cur_course_name
        self.ui.hw_selecter.clear()
        self.ui.hw_selecter.addItems(self.hw_folders[cur_select])

    def closeEvent(self, event) -> None:
        # Clost ftp connectoin
        if self.downloader.ftp != None:
            self.downloader.ftp.quit()
            print("結束連線")

    @property
    def cur_course_name(self):
        return self.ui.course_selecter.currentText()
    @property
    def cur_hw(self):
        return self.ui.hw_selecter.currentText()
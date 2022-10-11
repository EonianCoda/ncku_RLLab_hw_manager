from collections import defaultdict
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox
from UI import Ui_Form
from hw_downloader import Hw_downloader
from threading import Thread
import os
import patoolib # for rar file
import threading
##TODO 時區轉換 +8 => +0
##TODO 平行化下載與解壓縮



FOLDER_PATH = "/Course/{}/Upload/Homework/"
COURSE_FOLDERS = ['CvDl_2022_G', 'OpenCvDl_2022_Bs']

def unzip(file_path : str, output_directory : str):
    os.makedirs(output_directory,exist_ok=True)
    patoolib.extract_archive(file_path, outdir=output_directory)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.downloader = Hw_downloader()

        self.ui.course_selecter.addItems(COURSE_FOLDERS)
        self.ui.course_selecter.currentTextChanged.connect(self.change_hw_options)
        self.submitted_files = None
        self.error_files = None
        self.ftp_target_path = None
        
        self.dlg = QMessageBox(self)
        # For testing
        self.hw_folders = {'CvDl_2022_G':['hw1_1'], 'OpenCvDl_2022_Bs':['hw1_1', 'hw_1_2']}
        self.ui.hw_selecter.addItems(['hw1_1', 'hw_1_2'])

        self.setup_control()
    def setup_control(self):
        self.ui.login_btn.clicked.connect(self.login_ftp)
        self.ui.set_search_path_btn.clicked.connect(self.set_search_path)
        self.ui.search_files_btn.clicked.connect(self.search_files)
        self.ui.download_hw_btn.clicked.connect(self.download_files)
        self.ui.output_data_btn.clicked.connect(self.output_data)
        self.ui.set_delay_time.clicked.connect(self.set_delay_time)
    
    def set_delay_time(self):
        date = self.ui.set_date.selectedDate()
        time = self.ui.set_time.time()
        self.ui.delay_time_show.setDate(date)
        self.ui.delay_time_show.setTime(time)

        # print(self.ui.delay_time_show.dateTime().toPyDateTime())
    def output_data(self):
        if self.submitted_files == None:
            return
        if self.downloader.ftp == None:
            self.show_not_connect_message()
            return
        
        contents = ["學號,姓名,最終版本,檔案名稱,最後更新時間,遲交\n"]

        delay_time = self.ui.delay_time_show.dateTime().toPyDateTime()
        for s_id, datas in self.submitted_files.items():
            max_version = 0
            max_idx = 0
            for i, data in enumerate(datas):
                v = data[-1]
                if v > max_version:
                    max_version = v
                    max_idx = i
            data = datas[max_idx]

            if data[0] > delay_time:
                delay = 1
            else:
                delay = 0
            line = "{},{},{},{},{},{}\n".format(s_id, data[2], data[3], data[1], data[0].strftime("%Y/%m/%d %H:%m"), delay)
            contents.append(line)
        
        file_name = "{}_{}.csv".format(self.ui.course_selecter.currentText(), self.ui.hw_selecter.currentText())
        with open(file_name, 'w', encoding='big5') as f:
            f.writelines(contents)

        if len(self.error_files) != 0:
            file_name = "{}_{}_error.csv".format(self.ui.course_selecter.currentText(), self.ui.hw_selecter.currentText())
            lines = [f + '\n' for f in self.error_files]
            with open(file_name, 'w', encoding='big5') as f:
                f.writelines(lines)
    
    def download_files(self):
        if self.submitted_files == None:
            return
        if self.downloader.ftp == None:
            self.show_not_connect_message()
            return

        file_paths = []
        
        root_dir = "./{}/{}/".format(self.ui.course_selecter.currentText(), self.ui.hw_selecter.currentText())
        for s_id, datas in self.submitted_files.items():
            max_version = 0
            max_idx = 0
            for i, data in enumerate(datas):
                v = data[-1]
                if v > max_version:
                    max_version = v
                    max_idx = i
            data = datas[max_idx]
            file_name = data[1]

            ftp_path = "{}/{}".format(self.ftp_target_path, file_name)
            output_path = os.path.join(root_dir, file_name)
            file_paths.append(output_path)
            self.downloader.download_file(ftp_path, output_path)


        file_name = "{}_{}_download_error.csv".format(self.ui.course_selecter.currentText(), self.ui.hw_selecter.currentText())
        

        error_zip_files = []
        # Auto unzip
        if self.ui.auto_unzip_ckb.isChecked():
            for file in file_paths:
                out_directory = os.path.basename(file)[:-4]
                output_path = os.path.join(root_dir, out_directory)
                try:
                    unzip(file, output_path)
                    os.remove(file)
                # unzip error
                except:
                    error_zip_files.append(os.path.basename(file))
            lines = [f + '\n' for f in error_zip_files]
            with open(file_name, 'w', encoding='big5') as f:
                f.writelines(lines)



    def show_not_connect_message(self):
        self.dlg.setWindowTitle("錯誤")
        self.dlg.setText("請先登入後再執行此功能")
        self.dlg.exec()
    def search_files(self):
        if self.downloader.ftp == None:
            self.show_not_connect_message()
            return
        path = self.ui.search_path_show.text()
        self.ftp_target_path = path
        files, success_count, error_count, error_files = self.downloader.list_hw_files(path)

        self.submitted_files = files
        self.error_files = error_files
        self.ui.available_files_label.setText("有效檔案: {}".format(success_count))
        self.ui.unavailable_files_label.setText("無效檔案: {}".format(error_count))
        self.ui.submitted_student_num_label.setText("繳交人數: {}".format(len(self.submitted_files)))

        self.ui.output_data_btn.setEnabled(True)
        self.ui.download_hw_btn.setEnabled(True)
    def set_search_path(self):
        cur_course = self.ui.course_selecter.currentText()
        cur_hw = self.ui.hw_selecter.currentText()
        path = FOLDER_PATH.format(cur_course) + cur_hw
        self.ui.search_path_show.setText(path)
        self.ui.search_files_btn.setEnabled(True)

    def login_ftp(self):
        success = self.downloader.connect(self.ui.username.text(), self.ui.password.text())
        
        if not success:
            self.dlg.setWindowTitle("登入失敗")
            self.dlg.setText("請重新登入")
            self.dlg.exec()
            return

        t = Thread(target=self.search_folders)
        t.start()
        self.dlg.setWindowTitle("登入成功")
        self.dlg.setText("歡迎使用")
        self.dlg.exec()
        t.join()

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
        cur_select = self.ui.course_selecter.currentText()
        self.ui.hw_selecter.clear()
        self.ui.hw_selecter.addItems(self.hw_folders[cur_select])

    def closeEvent(self, event) -> None:
        # Clost ftp connectoin
        if self.downloader.ftp != None:
            self.downloader.ftp.quit()
            print("結束連線")
        #return super().closeEvent(a0)
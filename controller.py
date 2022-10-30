import shutil
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem, QWidget
from PyQt5.QtCore import QThread, pyqtSignal
import PyQt5
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFileDialog, QAbstractButton
from UI import Ui_Form
from hw_downloader import Hw_downloader
from collections import defaultdict
import os
import patoolib # for rar file
import pickle
import ftplib
from pathlib import Path
from collections import defaultdict
from functools import cmp_to_key
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.styles.colors import Color
from openpyxl.styles.borders import Border, Side

FOLDER_PATH = "/Course/{}/Upload/Homework/"
# Course List
COURSE_FOLDERS = ['CvDl_2022_G', 'OpenCvDl_2022_Bs']
# CSV file contains the student's name and id
COURSE_STUDENT_LIST = ['./course_data/cvdl_students.csv', './course_data/opencvdl_students.csv']
TA_WHITE_LIST = ["./course_data/cvdl_TA_whitelist.csv", "./course_data/opencvdl_TA_whitelist.csv"]

LOGIN_INFO = "login.key"
DOWNLOAD_FILE_ROOT = Path("./download")

##################### For Debug #########################
# if os.path.isdir(DOWNLOAD_FILE_ROOT):
#     shutil.rmtree(DOWNLOAD_FILE_ROOT)
##TODO 遲交分數比例
##TODO 匯入group
##TODO 新增下載log，避免多次重覆下載 
##TODO 新增開啟excel, 資料夾選項
##TODO List Directory timeout problem

##TODO GIF圖檔失真


login_success_styleSheet = """
QLabel
{	
	font: 75 20pt "微軟正黑體";
	font-weight:bold;
	color: green;
}
"""
def unzip(file_path : str, output_directory : str):
    """Unzip a zip file into directory
    Args:
        file_path: the path for zip file
        output_directory: the path for extract the zip file
    """
    os.makedirs(output_directory, exist_ok=True)
    output_directory = str(output_directory)
    file_path = str(file_path)
    patoolib.extract_archive(file_path, outdir=output_directory)

def find_final_version(datas : list):
    """Use timestamp to find the latest version homework
    """
    max_timestamp = datas[0]['timestamp']
    max_idx = 0
    for i, data in enumerate(datas[1:]):
        if data['timestamp'] > max_timestamp:
            max_timestamp = data['timestamp']
            max_idx = i
    return datas[max_idx]

def clear_QTable(table):
    cur_row = table.rowCount()
    for _ in range(cur_row):
        table.removeRow(0)
    cur_col = table.columnCount()
    for _ in range(cur_col):
        table.removeColumn(0)

def compare_time(t1 : str, t2 :str):
    h1 = int(t1[0:2])
    h2 = int(t2[0:2])
    m1 = int(t1[3:5])
    m2 = int(t2[3:5])
    if h1 > h2 or (h1 == h2 and m1 > m2):
        return 1
    elif h1 < h2 or (h1 == h2 and m1 < m2):
        return -1
    else:
        return 0
def set_xlsx_row_border(sheet, row, border_style):
    for row in sheet.iter_rows(min_row=row, min_col=1, max_row=row, max_col=50):
        for cell in row:
            cell.border = border_style
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
        reconnect_times = 0
        remove_list = []
        # Download Files
        for idx, (s_id, datas) in enumerate(self.submitted_files.items()):
            data = find_final_version(datas)
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

        # Remove File which failed to download
        for f in remove_list:
            os.remove(f)

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

        
        self.ui.course_selecter.addItems(COURSE_FOLDERS)
        self.ui.course_selecter.currentTextChanged.connect(self.change_hw_options)
        self.submitted_files = None
        self.error_files = None
        self.ftp_target_path = None
        self.download_thread = None
        # Set Dialogue box and loading progress bar
        self.dlg = QMessageBox(self)
        self.loading_bar = LoadingProgress(self)
        self.setup_control()
        self.ui.course_selecter.setEnabled(False)
        self.ui.hw_selecter.setEnabled(False)

        # Load TA white list
        self.TA_whitelist = defaultdict(list)
        for course, csv_file in zip(COURSE_FOLDERS, TA_WHITE_LIST):
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line != "":
                    self.TA_whitelist[course].append(line.upper())

        # Load Students csv file
        self.student_IDS = defaultdict(list)
        self.student_names = defaultdict(list)
        self.student_major = defaultdict(list)
        for course, csv_file in zip(COURSE_FOLDERS, COURSE_STUDENT_LIST):
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            white_list = self.TA_whitelist[course]
            for line in lines[1:]:
                line = line.replace("\u3000",'').replace("\n",'')
                data = line.split(',')
                name = data[0]
                stdID = data[3].strip().upper()
                major = data[4]
                if len(stdID) != 9 or stdID in white_list:
                    continue
                self.student_names[course].append(name)
                self.student_IDS[course].append(stdID)
                self.student_major[course].append(major)

        # Set downloader
        self.downloader = Hw_downloader(student_IDS = self.student_IDS,
                                        student_names = self.student_names)

        # If account log exist, then read it and auto login
        if os.path.isfile(LOGIN_INFO):
            with open("login.key", 'rb') as f:
                username, password, auto_login = pickle.load(f)
            self.ui.username.setText(username)
            self.ui.password.setText(password)
            self.ui.auto_login_checkBox.setChecked(auto_login)
            # Auto login
            if auto_login:
                self.login_ftp()

        clear_QTable(self.ui.set_group_table)
        # corner = self.ui.set_group_table.findChild(QAbstractButton)
        # corner.setCheckable(True)
        # corner.clicked.connect(lambda checked, col=0, all_flag=True :self.group_table_select_all(checked, col, all_flag))
    def group_table_select_all(self, checked : bool, col : int, all_flag=False):
        # Select All
        if all_flag:
            max_row = self.ui.set_group_table.rowCount()
            max_col = self.ui.set_group_table.columnCount()
            for row in range(max_row):
                for col in range(max_col):
                    cell = self.ui.set_group_table.cellWidget(row, col)
                    if cell != None:
                        cell.setChecked(checked)
            return
        # Seletct one column
        max_row = self.ui.set_group_table.rowCount()
        for row in range(max_row):
            cell = self.ui.set_group_table.cellWidget(row, col)
            if cell != None:
                cell.setChecked(checked)
        
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

        self.ui.read_demo_time_file_btn.clicked.connect(self.select_demo_file)

        self.ui.download_hw_from_selection_btn.clicked.connect(self.download_from_selection)
    def download_from_selection(self):
        #self.ui.set_group_table
        pass
    def select_demo_file(self):
        clear_QTable(self.ui.set_group_table)
        filename, filetype = QFileDialog.getOpenFileName(self,
                                                        caption="Open file",
                                                        directory="./",
                                                        filter="Csv Files (*.csv)")
        
        if filename == "":
            return
        if self.ui.am_num_TA_input.text() == "" or self.ui.pm_num_TA_input.text() == "":
            self.dlg.setWindowTitle("警告")
            self.dlg.setText("請先填入上/下午分組數")
            self.dlg.exec()
            return
        num_TA = [int(self.ui.am_num_TA_input.text()), int(self.ui.pm_num_TA_input.text())]
        self.process_group_data(filename, num_TA)
    
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

        self.ui.course_selecter.setEnabled(True)
        self.ui.hw_selecter.setEnabled(True)
        return True
    def login_and_store(self):
        success = self.login_ftp()
        # Store password
        if success:
            username = self.ui.username.text()
            password = self.ui.password.text()
            auto_login = self.ui.auto_login_checkBox.isChecked()
            with open("login.key", 'wb') as f:
                pickle.dump((username, password, auto_login), f)


    def set_delay_time(self):
        date = self.ui.set_date.selectedDate()
        time = self.ui.set_time.time()
        self.ui.delay_time_show.setDate(date)
        self.ui.delay_time_show.setTime(time)

    def output_submitted_info(self):
        if not self.check_login() or self.submitted_files == None:
            return
        
        contents = ["學號,姓名,科系,最終版本,檔案名稱,檔案上傳時間,檔案大小(MB),是否遲交\n"]

        delay_time = self.ui.delay_time_show.dateTime().toPyDateTime()

        delay_count = 0
        no_submit_count = 0
        total_size = 0
        
        student_ids = self.student_IDS[self.cur_course_name]
        student_names = self.student_names[self.cur_course_name]
        student_major = self.student_major[self.cur_course_name]
        # white_list = self.TA_whitelist[self.cur_course_name]
        sorted_idx = sorted(range(len(student_ids)), key=lambda k : student_ids[k])
        for idx in sorted_idx:
            s_id = student_ids[idx]
            # if s_id.upper() in white_list:
            #     continue
            name = student_names[idx]
            major = student_major[idx]
            if self.submitted_files.get(s_id) == None:
                line = "{},{},{},,,,,\n".format(s_id.upper(), name, major)
                contents.append(line)
                no_submit_count += 1
                continue

            datas = self.submitted_files[s_id]
            data = find_final_version(datas)
            if data['timestamp'] > delay_time:
                delay_count += 1
                delay = 1
            else:
                delay = 0
            total_size += float(data['file_size'])
            line = "{},{},{},{},{},{},{},{}\n".format(s_id.upper(), 
                                                    data['chinese_name'],
                                                    major,
                                                    data['version'],
                                                    data['file_name'],
                                                    data['timestamp'].strftime("%Y/%m/%d %H:%m"), 
                                                    data['file_size'], 
                                                    delay)
            contents.append(line)
        
        csv_file_name = "{}.csv".format(self.cur_hw)
        output_path = DOWNLOAD_FILE_ROOT / self.cur_course_name
        os.makedirs(output_path, exist_ok=True)
        # Write Error log
        with open(output_path / csv_file_name, 'w', encoding='utf-8') as f:
            f.write('\ufeff')
            f.writelines(contents)
        # Update UI
        self.ui.delay_submitted_student_num_label.setText("遲交人數: {}".format(delay_count))
        self.ui.total_file_size_label.setText("總檔案大小: {:.2f}G".format(total_size / 1024))
        self.ui.no_submitted_student_num_label.setText("未繳人數: {}".format(no_submit_count))

        if len(self.error_files) != 0:
            file_name = "{}_submit_error.csv".format(self.cur_hw)
            lines = ["檔案名稱,錯誤訊息\n"]
            for info in self.error_files:
                f = info[0]
                error_msg = info[1]
                lines.append("{},{}\n".format(f, error_msg))
            with open(output_path / file_name, 'w', encoding='utf-8') as f:
                f.write('\ufeff')
                f.writelines(lines)
        os.system("start EXCEL.EXE {}".format(str(output_path / csv_file_name)))

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

    def process_group_data(self, group_csv_file:list, num_TA:tuple):
        """Process group data
        Args:
            group_csv_file: the path of group csv file
            num_TA: a tuple contains two value, first value means the number of TA in the morning, Second value means the number of TA in the afternonn
        """
        def create_cb_item():
            cb = QtWidgets.QCheckBox(parent=self.ui.set_group_table)
            cb.setStyleSheet("margin-left:10%; margin-right:10%;")
            return cb
        with open(group_csv_file,'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Set Table Header
        max_TA_num = max(num_TA)
        mark = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        self.ui.set_group_table.insertColumn(0)
        header = ['時段']
        for m in mark[:max_TA_num]:
            self.ui.set_group_table.insertColumn(0)
            header.append('{}組'.format(m))
        self.ui.set_group_table.setHorizontalHeaderLabels(header)

        self.ui.set_group_table.insertRow(0)
        # Set select all
        cb = create_cb_item()
        cb.clicked.connect(lambda checked: self.group_table_select_all(checked, 0, all_flag=True))
        self.ui.set_group_table.setCellWidget(0, 0, cb)

        for col in range(1, max_TA_num + 1):
            cb = create_cb_item()
            cb.clicked.connect(lambda checked, col=col: self.group_table_select_all(checked, col))
            self.ui.set_group_table.setCellWidget(0, col, cb)

        time_txt = "{:02d}:00-{:02d}:00"
        timestamps = []
        num_TA_per_time = []
        num_student = 0

        for i in range(9):
            hour = 9 + i
            timestamp = time_txt.format(hour, hour + 1)
            timestamps.append(timestamp)

        student_name = dict()
        datas = defaultdict(list)
        for line in lines[1:]:
            data = line.split(',')
            s_id = data[2]
            selection = data[4]
            # Invalid Student id
            if len(s_id) != 9:
                continue
            # No Selection
            if selection == "":
                continue
            
            # Store student_name
            student_name[s_id] = data[1]

            idx = (int(selection[5:]) - 1) // 4
            timestamp = timestamps[idx]
            num_student += 1
            datas[timestamp].append(s_id)

        sorted_times = sorted(datas.keys(), key=cmp_to_key(compare_time))

        for time_key in sorted_times:
            s_ids = datas[time_key]
            s_ids = sorted(s_ids)
            datas[time_key] = s_ids

            hour = int(time_key[:2])
            # Afternoon
            if hour >= 13:
                num_TA_per_time.append(num_TA[1])
            else:
                num_TA_per_time.append(num_TA[0])

            # Update table
            cur_row = self.ui.set_group_table.rowCount()
            self.ui.set_group_table.insertRow(cur_row)
            # Add timestamp
            item = QTableWidgetItem(time_key)
            item.setTextAlignment(PyQt5.QtCore.Qt.AlignCenter)
            self.ui.set_group_table.setItem(cur_row, 0, item)

            for col in range(1, num_TA_per_time[-1] + 1):
                cb = create_cb_item()
                self.ui.set_group_table.setCellWidget(cur_row, col, cb)
        vertical_header = ['全選'] + [''] * len(sorted_times)
        self.ui.set_group_table.setVerticalHeaderLabels(vertical_header)

        self.ui.set_group_table.resizeColumnsToContents()

        # Style
        middle_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        workbook = openpyxl.Workbook()
        sheet = workbook.worksheets[0]
        # Add header
        sheet.append(['時間','分組','姓名','學號'])
        set_xlsx_row_border(sheet, 1, Border(bottom=Side(style='medium')))

        ### Set Timestamp ###
        cur_row = 2
        for time_key in sorted_times:
            # Set Time stamp
            timestamp = "{}\n~\n{}".format(time_key[0:5],time_key[-5:])
            cell = sheet.cell(row=cur_row, 
                            column=1, 
                            value = timestamp)
            # Set Style
            cell.font = Font(size=12, bold=True)
            cell.alignment = middle_alignment
            cell.border = Border(right=Side(style='thin'))
            set_xlsx_row_border(sheet, 
                                cur_row + len(datas[time_key]) - 1, 
                                Border(bottom=Side(style='medium')))
            # Merge Cell
            sheet.merge_cells(start_row=cur_row,
                                end_row=cur_row + len(datas[time_key]) - 1,
                                start_column=1,
                                end_column=1)
            cur_row += len(datas[time_key])
            
        ### Set group and student ###
        cur_row = 2
        for time_key, num_group in zip(sorted_times, num_TA_per_time):
            time_group_data = datas[time_key]

            # Compute number for each group
            per_num = len(time_group_data) // num_group
            per_student_group = [per_num] * num_group
            for i in range(len(time_group_data) - per_num * num_group):
                per_student_group[i] += 1
            
            cur_color_idx = 0
            cur_student_idx = 0
            for mark_idx, num in enumerate(per_student_group):
                if num == 0:
                    continue
                group_name = "{}組".format(mark[mark_idx])
                
                cell = sheet.cell(row=cur_row, 
                                    column=2, 
                                    value = group_name)
                # Set Style
                cell.font = Font(bold=True)
                cell.alignment =middle_alignment
                color_index = (45 + cur_color_idx) % 64
                # Color index = 0 is black
                if color_index == 0:
                    color_index = 1
                    cur_color_idx += 1
                cell.fill = PatternFill('solid', Color(index=color_index))
                # Merge Cell
                sheet.merge_cells(start_row=cur_row,
                                end_row=cur_row + num - 1,
                                start_column=2,
                                end_column=2)
                # Student ids
                for i, s_id in enumerate(time_group_data[cur_student_idx : cur_student_idx+num]):
                    name = student_name[s_id]
                    sheet.cell(row=cur_row + i, column=3, value = name)
                    sheet.cell(row=cur_row + i, column=4, value = s_id)
                cur_student_idx += num
                cur_row += num
                cur_color_idx += 1

        # Save File
        workbook.save('test.xlsx')
    def search_folders(self):
        """Search homework folders
        """
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
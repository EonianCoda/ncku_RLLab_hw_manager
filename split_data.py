csv_file = "opencvdl_分組名單_test.csv"
with open(csv_file,'r', encoding="utf-8") as f:
    lines = f.readlines()

timed_data = dict()
cur_dict = None
cur_list = None
for line in lines[1:]:
    if '"' in line and ',' not in line:
        timestamp = line.strip().replace('"','')
        continue
    elif ',' not in line:
        timestamp += line.strip()
        continue

    datas = line.split(',')
    if '"' in line:
        timestamp += datas[0].replace('"','')
        cur_dict = dict()
        timed_data[timestamp] = cur_dict

    group = datas[1]
    if group != "":
        group = group.replace("組",'')
        cur_list = list()
        cur_dict[group] = cur_list

    s_id = datas[3]
    cur_list.append(s_id)
with open('./download/OpenCvDl_2022_Bs/hw1.csv', 'r',encoding='utf-8') as f:
    lines = f.readlines()

hw_mapping = dict()
s_names = dict()
header = lines[0].split(',')
hw_header = [header[i].replace('名稱','') for i in range(3, len(header),3)]
for line in lines[1:]:
    datas = line.split(',')
    s_id = datas[0]
    name = datas[1]
    s_names[s_id] = name
    hw_files = [datas[i] for i in range(3, len(datas),3)]
    hw_mapping[s_id] = hw_files

import os
import shutil
file_root = "E:\\"

old_root = os.path.join(file_root, 'hw_files')
new_root = os.path.join(file_root, 'group_hw_files')
os.makedirs(new_root, exist_ok=True)
for timestamp, grouped_data in timed_data.items():
    timestamp = timestamp.replace(":",'').replace('~','-')
    for group_idx, s_ids in grouped_data.items():
        for s_id in s_ids:
            new_path = os.path.join(new_root, group_idx, timestamp, s_id)
            os.makedirs(new_path, exist_ok=True)

            for hw_head, file_name in zip(hw_header, hw_mapping[s_id]):
                if file_name == "":
                    continue
                old_path = os.path.join(old_root, hw_head, file_name)
                if not os.path.exists(old_path):
                    continue
                shutil.move(old_path, os.path.join(new_path, file_name))
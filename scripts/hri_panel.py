#!/usr/bin/env python3
"""Voice/gesture drives immediately; confirmation is required only for saving."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk

import rclpy
from std_msgs.msg import String,Bool
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile,DurabilityPolicy


def main():
    rclpy.init()
    node=rclpy.create_node('lab_hri_panel')
    decision_pub=node.create_publisher(String,'/hri/decision',10)
    listening_pub=node.create_publisher(String,'/hri/listening_state',10)
    mapping_pub=node.create_publisher(String,'/mapping/control',10)
    voice_pub=node.create_publisher(String,'/hri/voice',10)
    session_pub=node.create_publisher(String,'/session/control',10)
    manual_pub=node.create_publisher(Twist,'/cmd_vel_manual',10)
    transcript_pub=node.create_publisher(String,'/voice_nav/transcript',10)
    root=tk.Tk();root.title('TurtleBot 4 — Giọng nói và xác nhận');root.geometry('900x'+str(min(760,root.winfo_screenheight()-80)))
    notebook=ttk.Notebook(root);notebook.pack(fill='both',expand=True)
    control_tab=ttk.Frame(notebook);map_tab=ttk.Frame(notebook)
    notebook.add(control_tab,text='ĐIỀU KHIỂN');notebook.add(map_tab,text='MAP VÀ ĐỊA ĐIỂM')
    canvas=tk.Canvas(control_tab,highlightthickness=0)
    scroll=ttk.Scrollbar(control_tab,orient='vertical',command=canvas.yview)
    scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    body=ttk.Frame(canvas);body_window=canvas.create_window((0,0),window=body,anchor='nw')
    body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(body_window,width=e.width))
    root.bind_all('<MouseWheel>',lambda e:canvas.yview_scroll(-int(e.delta/120),'units'))
    project=Path(__file__).resolve().parents[1]
    runtime=Path('/tmp')/f'tb4_cuoiky_runtime_{os.getuid()}'
    runtime.mkdir(exist_ok=True)
    panel_pid=runtime/'panel.pid';panel_pid.write_text(str(os.getpid()))
    current={'request_id':None,'worker':None,'enabled':False,'generation':0,'closed':False,'speaking':False,'speech_intervals':[],'camera_enabled':os.environ.get('TB4_AUTO_CAMERA','1')=='1','needs_answer':False,'mode':'stop','mapping_session':True}
    messages=queue.Queue()
    status=tk.StringVar(value='Đang chờ lệnh từ người dùng')
    destination=tk.StringVar(value='Sẵn sàng nhận lệnh giọng nói hoặc cử chỉ')
    noisy=tk.BooleanVar(value=False)
    ttk.Checkbutton(body,text='Phòng ồn / nhiều người: gọi “Robot” trước mỗi câu lệnh',variable=noisy).pack()
    def speech_state(m):
        current['speaking']=m.data
        now=time.time()
        if m.data:current['speech_intervals'].append([now,float('inf')])
        elif current['speech_intervals']:current['speech_intervals'][-1][1]=now+.5
        current['speech_intervals']=current['speech_intervals'][-12:]
    node.create_subscription(Bool,'/hri/speech_active',speech_state,10)
    recording=tk.StringVar(value='Đang chuẩn bị chế độ nói trực tiếp…' if os.environ.get('TB4_AUTO_MIC','1')=='1' else 'Micro đã tạm dừng')
    transcript=tk.StringVar(value='Văn bản nhận dạng sẽ xuất hiện tại đây')
    ttk.Label(body,text='TurtleBot 4 · Tương tác người–robot',font=('',18)).pack(pady=6)
    ttk.Label(body,text='1 / 2 / 3 ngón → địa điểm 1 / 2 / 3 đã gán  |  Ngón cái → xác nhận lưu map / địa điểm').pack(pady=4)
    ttk.Label(body,textvariable=recording,wraplength=710).pack(pady=4)
    ttk.Label(body,textvariable=transcript,wraplength=710,font=('',13)).pack(pady=4)

    def stop_listening():
        listening_pub.publish(String(data='done'))
        current['enabled']=False;current['generation']+=1
        process=current['worker'];current['worker']=None
        if process and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        talk.config(text='BẬT MICRO')
        recording.set('Micro đã tạm dừng')

    def start_listening():
        if current['enabled'] or current['closed']:return
        current['enabled']=True;current['generation']+=1
        generation=current['generation']
        talk.config(text='TẠM DỪNG MICRO');recording.set('Đang tải nhận dạng tiếng Việt…')
        def work():
            try:
                process=subprocess.Popen([str(project/'.venv-voice/bin/python'),
                    str(project/'scripts/continuous_voice_worker.py')],stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,text=True,start_new_session=True)
                if current['closed'] or generation!=current['generation']:
                    os.killpg(process.pid,signal.SIGTERM);process.wait();return
                current['worker']=process
                for line in process.stdout:
                    try:messages.put((generation,json.loads(line)))
                    except ValueError:pass
                if process.wait()!=0:messages.put((generation,dict(stage='error',message='Bộ nghe đã dừng; bấm BẬT MICRO để thử lại')))
            except Exception as exc:messages.put((generation,dict(stage='error',message=str(exc))))
            finally:messages.put((generation,dict(stage='done')))
        threading.Thread(target=work,daemon=True).start()

    def toggle_microphone():
        if current['enabled']:stop_listening()
        else:start_listening()

    talk=ttk.Button(body,text='TẠM DỪNG MICRO' if os.environ.get('TB4_AUTO_MIC','1')=='1' else 'BẬT MICRO',command=toggle_microphone)
    talk.pack(pady=4,ipadx=20,ipady=3)
    camera_pub=node.create_publisher(Bool,'/hri/camera_enabled',10)
    def toggle_camera():
        current['camera_enabled']=not current['camera_enabled']
        camera_pub.publish(Bool(data=current['camera_enabled']))
        camera_button.config(text='TẠM DỪNG CAMERA' if current['camera_enabled'] else 'BẬT CAMERA')
    camera_button=ttk.Button(body,text='TẠM DỪNG CAMERA',command=toggle_camera)
    camera_button.pack(pady=3)
    if not current['camera_enabled']:camera_button.config(text='BẬT CAMERA')
    def camera_state(m):
        current['camera_enabled']=m.data
        camera_button.config(text='TẠM DỪNG CAMERA' if m.data else 'BẬT CAMERA')
    node.create_subscription(Bool,'/hri/camera_enabled',camera_state,10)
    node.create_subscription(Bool,'/hri/microphone_enabled',lambda m:start_listening() if m.data else stop_listening(),10)
    entry=ttk.Entry(body,width=65)
    entry.pack(pady=4)
    def send_text(event=None):
        if entry.get().strip():voice_pub.publish(String(data=entry.get().strip()));entry.delete(0,'end')
    entry.bind('<Return>',send_text)
    ttk.Button(body,text='GỬI LỆNH / TRẢ LỜI',command=send_text).pack()
    ttk.Separator(body,orient='horizontal').pack(fill='x',padx=24,pady=4)
    ttk.Label(body,textvariable=destination,wraplength=710,font=('',14)).pack(pady=4)
    ttk.Label(body,textvariable=status,wraplength=710).pack(pady=4)

    def decision(action):
        stop_drive()
        decision_pub.publish(String(data=json.dumps(dict(action=action,request_id=current['request_id']))))
        confirm.config(state='disabled')

    confirm=ttk.Button(body,text='XÁC NHẬN LƯU',command=lambda:decision('confirm_save'),state='disabled')
    confirm.pack(pady=4,ipadx=25,ipady=3)
    modes=ttk.Frame(body);modes.pack()
    def set_mode(mode):
        stop_drive()
        mapping_pub.publish(String(data=mode));session_pub.publish(String(data=mode))
    mode_buttons={}
    for label,mode in [('QUÉT TỰ ĐỘNG','auto'),('THỦ CÔNG','manual'),('DỪNG QUÉT','stop')]:
        b=ttk.Button(modes,text=label,command=lambda m=mode:set_mode(m));b.pack(side='left',padx=4);mode_buttons[mode]=b
    ttk.Button(body,text='DỪNG / HỦY HÀNH TRÌNH',command=lambda:decision('stop')).pack(pady=4)

    drive={'vx':0.,'wz':0.,'until':0.,'mouse':False}
    def stop_drive(event=None):drive.update(vx=0.,wz=0.,until=0.,mouse=False)
    def press_drive(vx,wz,mouse=False):
        if current['mode']!='manual':return
        drive.update(vx=vx,wz=wz,until=time.monotonic()+.35,mouse=mouse)
    teleop=ttk.LabelFrame(body,text='Điều khiển tay: chọn THỦ CÔNG, giữ nút hoặc W/A/S/D')
    teleop.pack(pady=5)
    for label,vx,wz in [('← A',0.,.4),('↑ W',.12,0.),('↓ S',-.12,0.),('D →',0.,-.4)]:
        b=ttk.Button(teleop,text=label);b.pack(side='left',padx=4,pady=4)
        b.bind('<ButtonPress-1>',lambda e,v=vx,w=wz:press_drive(v,w,True))
        b.bind('<ButtonRelease-1>',stop_drive);b.bind('<Leave>',stop_drive)
    def key_press(event):
        if event.widget.winfo_class() in ('Entry','TEntry','TCombobox','Text'):return
        v,w={'w':(.12,0.),'s':(-.12,0.),'a':(0.,.4),'d':(0.,-.4)}.get(event.keysym.lower(),(0.,0.))
        press_drive(v,w)
    root.bind('<KeyPress>',key_press);root.bind('<KeyRelease>',stop_drive);root.bind('<FocusOut>',stop_drive)
    mode_text=tk.StringVar(value='Chế độ: chờ phiên làm việc')
    ttk.Label(body,textvariable=mode_text).pack(pady=3)
    def on_mode(m):
        if current['mode']!=m.data:stop_drive()
        current['mode']=m.data;mode_text.set('Chế độ: '+dict(manual='THỦ CÔNG',auto='QUÉT TỰ ĐỘNG',stop='DỪNG',navigation='ĐIỀU HƯỚNG').get(m.data,m.data))
    node.create_subscription(String,'/mapping/mode',on_mode,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))

    map_state=tk.StringVar(value='Đang chờ map…')
    ttk.Label(map_tab,textvariable=map_state,font=('',13)).pack(pady=12)
    ttk.Label(map_tab,text='1. Quét tự động hoặc điều khiển tay → DỪNG QUÉT → lưu map.\n2. Sau khi lưu map, đặt tên cho vị trí xe hoặc chọn điểm trên RViz.',wraplength=820).pack(pady=8)
    map_name=tk.StringVar(value='phòng lab mới')
    map_row=ttk.LabelFrame(map_tab,text='Lưu bản đồ đang quét');map_row.pack(fill='x',padx=16,pady=8)
    ttk.Entry(map_row,textvariable=map_name,width=42).pack(side='left',padx=8,pady=8)
    ttk.Button(map_row,text='LƯU MAP',command=lambda:voice_pub.publish(String(data='Lưu bản đồ '+map_name.get().strip()))).pack(side='left',padx=8)
    point_row=ttk.LabelFrame(map_tab,text='Đặt địa điểm tùy ý');point_row.pack(fill='x',padx=16,pady=8)
    place_name=tk.StringVar();ttk.Entry(point_row,textvariable=place_name,width=45).pack(pady=8)
    ttk.Label(point_row,text='Nhập tên địa điểm. Điểm chọn phải ở vùng trắng, đủ xa tường/vật cản.',wraplength=790).pack(pady=4)
    place_buttons=ttk.Frame(point_row);place_buttons.pack(pady=8)
    current_place=ttk.Button(place_buttons,text='LƯU VỊ TRÍ XE',state='disabled',command=lambda:voice_pub.publish(String(data='Lưu địa điểm '+place_name.get().strip())))
    current_place.pack(side='left',padx=5)
    selected_place=ttk.Button(place_buttons,text='LƯU ĐIỂM ĐÃ CHỌN',state='disabled',command=lambda:decision_pub.publish(String(data=json.dumps(dict(action='prepare_selected_place',name=place_name.get().strip())))))
    selected_place.pack(side='left',padx=5)
    ttk.Label(point_row,text='Chọn điểm: bấm Publish Point trên RViz rồi click vị trí muốn lưu.\nChọn điểm chỉ đánh dấu, không làm robot chạy.',wraplength=790).pack(pady=5)
    map_prompt=tk.StringVar(value='Chỉ xác nhận khi lưu map hoặc địa điểm.')
    ttk.Label(map_tab,textvariable=map_prompt,wraplength=820).pack(pady=8)
    map_confirm=ttk.Button(map_tab,text='XÁC NHẬN LƯU',state='disabled',command=lambda:decision('confirm_save'));map_confirm.pack(pady=4)
    choices=ttk.Combobox(map_tab,state='readonly',width=55);choices.pack(pady=10)
    go_place=ttk.Button(map_tab,text='ĐI ĐẾN ĐỊA ĐIỂM ĐÃ CHỌN',state='disabled',command=lambda:voice_pub.publish(String(data='Đi đến '+choices.get())))
    go_place.pack(pady=5)
    delete_place=ttk.Button(map_tab,text='XÓA ĐỊA ĐIỂM ĐÃ CHỌN',state='disabled',command=lambda:voice_pub.publish(String(data='Xóa địa điểm '+choices.get())))
    delete_place.pack(pady=6)
    def on_catalog(m):
        try:
            d=json.loads(m.data);current['mapping_session']=d['mapping_session']
            map_state.set('ĐANG QUÉT MAP' if d['mapping_session'] else 'MAP ĐÃ LƯU — có thể dạy địa điểm và điều hướng')
            names=[r['name'] for r in d['places']];choices['values']=names
            if names and choices.get() not in names:choices.set(names[0])
            elif not names:choices.set('')
            enabled='normal' if not d['mapping_session'] and d.get('ready_to_save',False) else 'disabled'
            current_place.config(state=enabled);selected_place.config(state=enabled)
            go_place.config(state=enabled if names else 'disabled');delete_place.config(state=enabled if names else 'disabled')
            mode_buttons['auto'].config(state='normal' if d['mapping_session'] else 'disabled')
            mode_buttons['stop'].config(state='normal' if d['mapping_session'] else 'disabled')
        except (ValueError,KeyError):pass
    node.create_subscription(String,'/hri/catalog',on_catalog,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))

    def on_status(msg):
        try:
            data=json.loads(msg.data)
            if data.get('prompt') or data.get('reason'):map_prompt.set(data.get('prompt',data.get('reason','')))
            if data['state']=='awaiting_save_confirmation':
                label='XÁC NHẬN XÓA' if data.get('operation')=='delete_place' else 'XÁC NHẬN LƯU'
                map_confirm.config(state='normal',text=label);confirm.config(text=label)
            elif data['state'] in ('saved','saving','save_failed','save_expired','cancelled','idle'):map_confirm.config(state='disabled')
            current['needs_answer']=data['state'] in ('clarify','conflict')
            labels={'ready':'Sẵn sàng','accepted':'Đã nhận lệnh','gesture_command':'Đã nhận cử chỉ',
                    'navigating':'Đang di chuyển','arrived':'Đã đến đích',
                    'awaiting_save_confirmation':'Chờ ngón cái hoặc nút xác nhận',
                    'saved':'Đã lưu','completed':'Hoàn thành','collecting':'Đang ghép hai kênh','merged':'Hai kênh cùng yêu cầu',
                    'conflict':'Hai kênh mâu thuẫn — cần chọn lại','clarify':'Cần nói rõ hơn',
                    'waiting_safety':'Dừng chờ an toàn','paused_safety':'Đang chờ an toàn','resuming':'Tiếp tục hành trình','saving':'Đang lưu','saved':'Đã lưu','save_failed':'Chưa lưu được','save_expired':'Yêu cầu lưu hết hạn',
                    'cancelling':'Đang dừng','cancelled':'Đã hủy hành trình',
                    'failed':'Không thể đến đích','rejected':'Chưa thực hiện lệnh',
                    'decision_rejected':'Chưa thể xác nhận','idle':'Đang chờ lệnh'}
            status.set(labels.get(data['state'],data['state'])+(' · '+data['reason'] if data.get('reason') else ''))
            if data['state']=='awaiting_save_confirmation':
                current['request_id']=data['request_id']
                destination.set(data.get('prompt', 'Xác nhận lưu '+data.get('name','')))
                confirm.config(state='normal')
            elif data['state'] not in ('rejected','decision_rejected'):
                if data['state'] in ('saved','saving','save_failed','save_expired','cancelled','idle','completed'):
                    current['request_id']=None
                    confirm.config(state='disabled')
                if data['state']=='navigating':
                    destination.set('ĐANG ĐI ĐẾN: '+data.get('destination',data.get('region','')))
                elif data['state']=='completed':destination.set('Đã hoàn thành. Sẵn sàng nhận lệnh mới.')
                elif data.get('prompt'):destination.set(data['prompt'])
                else:destination.set('Trạng thái: '+data['state'])
        except (ValueError,KeyError,TypeError):status.set('Trạng thái không hợp lệ')

    node.create_subscription(String,'/hri/status',on_status,20)
    safety_text=tk.StringVar(value='Đang chờ cảm biến an toàn')
    ttk.Label(body,textvariable=safety_text).pack(pady=5)
    def safety_update(m):
        d=json.loads(m.data);safety_text.set('An toàn: '+d.get('state',''))
    node.create_subscription(String,'/hri/safety',safety_update,10)

    def poll():
        if not rclpy.ok():
            current['closed']=True;stop_listening();root.destroy();return
        rclpy.spin_once(node,timeout_sec=0)
        if current['mode']=='manual':
            m=Twist()
            if drive['mouse'] or time.monotonic()<drive['until']:m.linear.x=drive['vx'];m.angular.z=drive['wz']
            manual_pub.publish(m)
        while not messages.empty():
            generation,item=messages.get()
            if generation!=current['generation']:continue
            stage=item.get('stage')
            if stage in ('speech','transcribing','listening','error','done'):listening_pub.publish(String(data=stage))
            if stage=='loading':recording.set('Đang tải nhận dạng tiếng Việt…')
            elif stage=='listening':recording.set('MICRO ĐANG NGHE — nói “Đi đến bàn số 1 / 2 / 3” hoặc “Dừng lại”')
            elif stage=='speech':recording.set('Đang nghe bạn nói…')
            elif stage=='transcribing':recording.set('Đang hiểu lệnh · micro vẫn nghe')
            elif stage in ('transcript','context_transcript'):
                if stage=='context_transcript' and not current['needs_answer']:continue
                transcript.set('Bạn nói: '+item['text'])
                transcript_pub.publish(String(data=item['text']))
                from semantic_map import normalize
                clean=normalize(item['text'])
                is_stop=clean in ('dung','dung lai','robot dung lai','huy')
                end=item.get('audio_end_unix',time.time());begin=end-item.get('audio_seconds',0)
                overlaps=any(begin<b and end>a for a,b in current['speech_intervals'])
                if (current['speaking'] or overlaps) and not is_stop:
                    recording.set('Robot đang phản hồi; chờ robot nói xong.');continue
                if noisy.get() and item.get('avg_logprob',0)<-.8 and not is_stop:
                    recording.set('Chưa nghe rõ trong tiếng ồn. Nói lại hoặc dùng cử chỉ.');continue
                if noisy.get() and not clean.startswith('robot ') and not is_stop:
                    recording.set('Chế độ phòng ồn: hãy gọi Robot trước lệnh.');continue
                voice_pub.publish(String(data=item['text']))
                recording.set('Đã gửi lệnh. Đến nơi tự hoàn thành; chỉ xác nhận khi lưu map / địa điểm.')
            elif stage=='error':recording.set('Lỗi: '+item['message'])
            elif stage=='done':
                current['enabled']=False;current['worker']=None;talk.config(text='BẬT MICRO')
        root.after(30,poll)

    def close():
        current['closed']=True;stop_listening()
        decision('stop')
        for _ in range(3):rclpy.spin_once(node,timeout_sec=.05)
        root.destroy()

    root.protocol('WM_DELETE_WINDOW',close);poll();root.after(300,start_listening) if os.environ.get('TB4_AUTO_MIC','1')=='1' else None
    try:root.mainloop()
    finally:
        current['closed']=True
        process=current['worker']
        if process and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        if panel_pid.exists() and panel_pid.read_text().strip()==str(os.getpid()):panel_pid.unlink()
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':main()

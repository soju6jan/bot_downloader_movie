# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback

# third-party
from flask import Blueprint, request, Response, send_file, render_template, redirect, jsonify, session, send_from_directory 
from flask_socketio import SocketIO, emit, send
from flask_login import login_user, logout_user, current_user, login_required

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, path_data, socketio, my_login_required
from framework.util import Util
from system.model import ModelSetting as SystemModelSetting
from framework.common.torrent.process import TorrentProcess

# 패키지
# 로그
package_name = __name__.split('.')[0]
logger = get_logger(package_name)

from .model import ModelSetting, ModelMovieItem
from .logic import Logic
from .logic_normal import LogicNormal

#########################################################


#########################################################
# 플러그인 공용                                       
#########################################################
blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

menu = {
    'main' : [package_name, '봇 다운로드 - 영화'],
    'sub' : [
        ['setting', '설정'], ['list', '목록'], ['log', '로그']
    ],
    'category' : 'torrent'
}

plugin_info = {
    'version' : '0.1.0.0',
    'name' : 'bot_downloader_movie',
    'category_name' : 'torrent',
    'developer' : 'soju6jan',
    'description' : '텔레그램 봇으로 수신한 정보로 영화 다운로드',
    'home' : 'https://github.com/soju6jan/bot_downloader_movie',
    'more' : '',
}

def plugin_load():
    Logic.plugin_load()

def plugin_unload():
    Logic.plugin_unload()

def process_telegram_data(data):
    LogicNormal.process_telegram_data(data)



#########################################################
# WEB Menu 
#########################################################
@blueprint.route('/')
def home():
    return redirect('/%s/list' % package_name)

@blueprint.route('/<sub>')
@login_required
def first_menu(sub): 
    logger.debug('DETAIL %s %s', package_name, sub)
    if sub == 'setting':
        arg = ModelSetting.to_dict()
        arg['package_name']  = package_name
        arg['scheduler'] = str(scheduler.is_include(package_name))
        arg['is_running'] = str(scheduler.is_running(package_name))
        ddns = SystemModelSetting.get('ddns')
        arg['rss_api'] = '%s/%s/api/rss' % (ddns, package_name)
        return render_template('%s_setting.html' % package_name, sub=sub, arg=arg)
    elif sub == 'list':
        arg = {'package_name' : package_name}
        arg['is_torrent_info_installed'] = False
        try:
            import torrent_info
            arg['is_torrent_info_installed'] = True
        except Exception as e: 
            pass
        arg['is_available_normal_download'] = False
        try:
            import downloader
            arg['is_available_normal_download'] = downloader.Logic.is_available_normal_download()
        except Exception as e: 
            pass
        arg['ddns'] = SystemModelSetting.get('ddns')
        arg['show_log'] = ModelSetting.get('show_log')
        return render_template('%s_list.html' % package_name, arg=arg)
    elif sub == 'log':
        return render_template('log.html', package=package_name)
    return render_template('sample.html', title='%s - %s' % (package_name, sub))

#########################################################
# For UI 
#########################################################
@blueprint.route('/ajax/<sub>', methods=['GET', 'POST'])
def ajax(sub):
    try:
        # 설정
        if sub == 'setting_save':
            ret = ModelSetting.setting_save(request)
            return jsonify(ret)
        elif sub == 'scheduler':
            go = request.form['scheduler']
            logger.debug('scheduler :%s', go)
            if go == 'true':
                Logic.scheduler_start()
            else:
                Logic.scheduler_stop()
            return jsonify(go)
        elif sub == 'reset_db':
            LogicNormal.reset_last_index()
            ret = Logic.reset_db()
            return jsonify(ret)
        elif sub == 'one_execute':
            ret = Logic.one_execute()
            return jsonify(ret)
        
        elif sub == 'reset_last_index':
            ret = LogicNormal.reset_last_index()
            return jsonify(ret)

        # 목록
        elif sub == 'web_list':
            ret = ModelMovieItem.web_list(request)
            ret['plex_server_hash'] = None
            try:
                import plex
                ret['plex_server_hash'] = plex.Logic.get_server_hash()
            except Exception, e:
                logger.error('not import plex')
            return jsonify(ret)
        elif sub == 'add_download':
            db_id = request.form['id']
            ret = LogicNormal.add_download(db_id)
            return jsonify(ret)
        elif sub == 'add_download_sub':
            db_id = request.form['id']
            index = request.form['index']
            ret = LogicNormal.add_download_sub(db_id, index)
            return jsonify(ret)
        elif sub == 'remove':
            ret = ModelMovieItem.remove(request.form['id'])
            return jsonify(ret)
        
        
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())  
        return jsonify('fail')   


#########################################################
# API
#########################################################
@blueprint.route('/api/<sub>', methods=['GET', 'POST'])
def api(sub):
    try:
        if sub == 'add_download':
            db_id = request.args.get('id')
            ret1 = LogicNormal.add_download(db_id)
            ret2 = LogicNormal.add_download_sub(db_id, -1)
            return jsonify(ret1)
        elif sub == 'rss':
            ret = ModelMovieItem.api_list(request)
            data = []
            for item in ret:
                entity = {}
                entity['title'] = item.filename
                entity['link'] = item.magnet
                entity['created_time'] = item.created_time
                data.append(entity)
                if item.sub is not None:
                    for idx, sub in enumerate(item.sub):
                        url = '%s/%s/api/attach?id=%s_%s' % (SystemModelSetting.get('ddns'), package_name, item.id, idx)
                        entity = {}
                        entity['title'] = sub[1]
                        entity['link'] = url
                        entity['created_time'] = item.created_time
                        data.append(entity)

            from framework.common.rss import RssUtil
            xml = RssUtil.make_rss(package_name, data)
            return Response(xml, mimetype='application/xml')
        elif sub == 'attach':
            tmp = request.args.get('id').split('_')
            entity = ModelMovieItem.get_by_id(tmp[0])
            if entity is not None:
                import requests
                import io
                session = requests.Session()

                page = get_html(session, entity.url)
                page = get_html(session, entity.sub[int(tmp[1])][0], referer=entity.url, stream=True)
                
                byteio = io.BytesIO()
                for chunk in page.iter_content(1024):
                    byteio.write(chunk)

                filedata = byteio.getvalue()
                logger.debug('LENGTH : %s', len(filedata))
                
                attach_filename = entity.sub[int(tmp[1])][1]
                if ModelSetting.get_bool('sub_change_filename'):
                    ext = os.path.splitext(attach_filename)[1].lower()
                    if ext in ['.smi', '.srt', '.ass']:
                        attach_filename = '%s%s' % (os.path.splitext(entity.filename)[0], ext)


                logger.debug('filename : %s', attach_filename)
                return send_file(
                    io.BytesIO(filedata),
                    mimetype='application/octet-stream',
                    as_attachment=True,
                    attachment_filename=attach_filename)

    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())



def get_html(session, url, referer=None, stream=False):
    try:
        import requests
        logger.debug('get_html :%s', url)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36',
            'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language' : 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer' : ''
        } 
        headers['Referer'] = '' if referer is None else referer
        page_content = session.get(url, headers=headers, stream=stream, verify=False)
        if stream:
            return page_content
        data = page_content.content
        #logger.debug(data)
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())
        logger.error('Known..')
    return data
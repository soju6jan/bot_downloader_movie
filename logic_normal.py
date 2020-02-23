# -*- coding: utf-8 -*-
#########################################################
# python
import os
import datetime
import traceback
import urllib

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_
from guessit import guessit

# sjva 공용
from framework import app, db, scheduler, path_app_root
from framework.job import Job
from framework.util import Util
from system.logic import SystemLogic
from framework.common.torrent.process import TorrentProcess

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelMovieItem


#########################################################
class LogicNormal(object):
    @staticmethod
    def process_telegram_data(data):
        try:
            ret = ModelMovieItem.process_telegram_data(data)
            logger.debug(ret)
            if ret is not None:
                if ModelSetting.get_bool('receive_info_send_telegram'):
                    from telegram_bot import TelegramHandle

                    msg = '😉 영화 정보 수신\n'
                    msg += '제목 : %s (%s)\n' % (ret.movie_title, ret.movie_year)
                    msg += '파일 : %s\n' % ret.filename
                    
                    if ret.daum_poster is not None:
                        TelegramHandle.sendMessage(ret.daum_poster, mime='photo')
                        pass
                    #url = '%s/%s/api/add_download?url=%s' % (SystemLogic.get_setting_value('ddns'), package_name, ret.magnet)
                    url = '%s/%s/api/add_download?id=%s' % (SystemLogic.get_setting_value('ddns'), package_name, ret.id)
                    msg += '\n➕ 다운로드 추가\n%s\n' % url
                    try:
                        if ret.movie_title is not None:
                            if ret.movie_target == 'imdb':
                                url = 'https://www.imdb.com/title/%s' % ret.movie_id
                                msg += '\n● IMDB 정보\n%s' % url
                            else:
                                url = 'https://movie.daum.net/moviedb/main?movieId=%s' % (ret.movie_id)
                                msg += '\n● Daum 정보\n%s' % url
                    except Exception as e: 
                        logger.error('Exception:%s', e)
                        logger.error(traceback.format_exc())  

                    TelegramHandle.sendMessage(msg)

                LogicNormal.invoke()
                TorrentProcess.receive_new_data(ret, package_name)
        except Exception, e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())

                
    @staticmethod
    def send_telegram_message(item):
        try:
            import telegram_bot
            msg = '😉 봇 다운로드 - 영화 처리결과\n'
            msg += '제목 : %s (%s)\n' % (item.movie_title, item.movie_year)
            msg += '파일 : %s\n' % item.filename

            if item.download_status == 'true':
                status_str = '✔조건일치 - 요청'
            elif item.download_status == 'false':
                status_str = '⛔패스 '
            elif item.download_status == 'no':
                status_str = '자동 다운로드 사용안함'
            elif item.download_status == 'true_only_status':
                status_str = '✔조건일치 - 상태만'
            elif item.download_status == 'false_only_status':
                status_str = '⛔조건불일치 - 상태만'

            msg += '결과 : %s\n' % status_str
            msg += '%s/%s/list\n' % (SystemLogic.get_setting_value('ddns'), package_name)
            msg += '로그\n' + item.log
            telegram_bot.TelegramHandle.sendMessage(msg)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())



    @staticmethod
    def reset_last_index():
        try:
            ModelSetting.set('last_id', '-1')
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    
    @staticmethod
    def invoke():
        try:
            logger.debug('invoke')
            telegram_invoke_action = ModelSetting.get('telegram_invoke_action')
            if telegram_invoke_action == '0':
                return False
            elif telegram_invoke_action == '1':
                if scheduler.is_include(package_name):
                    if scheduler.is_running(package_name):
                        return False
                    else:
                        scheduler.execute_job(package_name)
                        return True
            elif telegram_invoke_action == '2':
                from .logic import Logic
                Logic.one_execute()
                return True
            else:
                return False
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())




    # 토렌트
    @staticmethod
    def add_download(db_id):
        try:
            import downloader
            item = ModelMovieItem.get_by_id(db_id)
            downloader_item_id = downloader.Logic.add_download2(item.magnet, ModelSetting.get('torrent_program'), ModelSetting.get('path'), request_type=package_name, request_sub_type='')['downloader_item_id']
            item.downloader_item_id = downloader_item_id
            item.download_status = item.download_status.replace('|manual', '')
            item.download_status = '%s|manual' % item.download_status
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
    

    # 자막
    @staticmethod
    def add_download_sub(db_id, index):
        try:
            import downloader
            item = ModelMovieItem.get_by_id(db_id)
            is_available_normal_download = downloader.Logic.is_available_normal_download()
            if is_available_normal_download and item.sub is not None:
                for idx, dummy in enumerate(item.sub):
                    if index == -1 or idx == index:
                        url = '%s/%s/api/attach?id=%s_%s' % (SystemLogic.get_setting_value('ddns'), package_name, item.id, idx)
                        downloader.Logic.add_download2(url, ModelSetting.get('torrent_program'), ModelSetting.get('path'), request_type=package_name, request_sub_type='')
                return True
            return False
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    


    


    

    @staticmethod
    def scheduler_function():
        try:
            last_id = ModelSetting.get_int('last_id')
            flag_first = False
            if last_id == -1:
                flag_first = True
                # 최초 실행은 -1로 판단하고, 봇을 설정안했다면 0으로
                query = db.session.query(ModelMovieItem) \
                    .filter(ModelMovieItem.created_time > datetime.datetime.now() + datetime.timedelta(days=-7))
                items = query.all()
            else:
                query = db.session.query(ModelMovieItem) \
                    .filter(ModelMovieItem.id > last_id )
                items = query.all()

            # 하나씩 판단....
            logger.debug('New Feed.. last_id:%s count :%s', last_id, len(items))
            for item in items:
                try:
                    flag_download = False
                    item.download_status = ''
                    item.downloader_item_id = None
                    item.log = ''

                    option_auto_download = ModelSetting.get('option_auto_download')
                    if option_auto_download == '0':
                        item.download_status = 'no'
                    else:
                        flag_download = LogicNormal.check_option_meta(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_target(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_country_include(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_country_exclude(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_year(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_genre_include(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_genre_exclude(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_rate(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_keyword_include(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_keyword_exclude(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_quality(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_source(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_video_codec(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_audio_codec(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_sub(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_plex(item)
                        if flag_download:
                            flag_download = LogicNormal.check_option_size(item)

                        #다운로드
                        if flag_download:
                            if option_auto_download == '1':
                                import downloader
                                downloader_item_id = downloader.Logic.add_download2(item.magnet, ModelSetting.get('torrent_program'), ModelSetting.get('path'), request_type=package_name, request_sub_type='')['downloader_item_id']
                                item.downloader_item_id = downloader_item_id
                                item.download_status = 'true'

                                is_available_normal_download = downloader.Logic.is_available_normal_download()
                                if is_available_normal_download and item.sub is not None:
                                    for idx, sub in enumerate(item.sub):
                                        url = '%s/%s/api/attach?id=%s_%s' % (SystemLogic.get_setting_value('ddns'), package_name, item.id, idx)

                                        downloader.Logic.add_download2(url, ModelSetting.get('torrent_program'), ModelSetting.get('path'), request_type=package_name, request_sub_type='')
                            else:
                                item.download_status = 'true_only_status'
                        else:
                            if option_auto_download == '1':
                                item.download_status = 'false'
                            else:
                                item.download_status = 'false_only_status'
                        
                    if ModelSetting.get_bool('download_start_send_telegram'):
                        LogicNormal.send_telegram_message(item)
                    db.session.add(item)
                except Exception as e: 
                    logger.error('Exception:%s', e)
                    logger.error(traceback.format_exc())

            new_last_id = last_id
            if flag_first and len(items) == 0:
                new_last_id = '0'
            else:
                if len(items) > 0:
                    new_last_id = '%s' % items[len(items)-1].id
            if new_last_id != last_id:
                ModelSetting.set('last_id', str(new_last_id))
            db.session.commit()

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_score(screen_size, source):
        screen_size_list = {'sd':1, '720':30, '1080':50, '4K':100, '2160':100}
        score = 0
        if screen_size in screen_size_list.keys():
            score += screen_size_list[screen_size]
        source_list = {'Blu-ray':100, 'Web':50, 'Ultra HD Blu-ray':100}
        if source in source_list.keys():
            score += source_list[source]
        return score


    # 16. option_plex
    @staticmethod
    def check_option_plex(item):
        try:
            log = ''
            flag_download = False
            value = ModelSetting.get('option_plex')
            if value == '0':
                flag_download = True
            elif value == '1':
                if not item.plex_info:
                    flag_download = True
                    log += u'Plex에 없음'
            elif value == '2':
                if item.plex_info:
                    if 'screen_size' not in item.guessit:
                        log += u'화질 정보없음'
                        flag_download = False
                    elif 'source' not in item.guessit:
                        flag_download = False
                        log += u'소스 정보없음'
                    else:
                        current_score = LogicNormal.get_score(item.guessit['screen_size'].replace('p', ''), item.guessit['source'])
                        if current_score == 0:
                            log += 'Plex : 세부정보 알수 없어서 제외'
                        else:
                            score_list = []
                            for v in item.plex_info:
                                for m in v['media']:
                                    s1 = m['info'].split('/')[0].strip()
                                    g = guessit(os.path.basename(m['file']))
                                    s2 = ''
                                    if 'source' in g:
                                        s2 = g['source']
                                    score_list.append(LogicNormal.get_score(s1, s2))
                            score_list = list(reversed(sorted(score_list)))
                            logger.debug('%s %s ', current_score, score_list)
                            if current_score <= score_list[0]:
                                log += u'Plex : 영상점수[%s] 최고점[%s] 제외' % (current_score, score_list[0])
                            else:
                                flag_download = True
                                log += u'Plex : 영상점수[%s] 최고점[%s]' % (current_score, score_list[0])
                else:
                    flag_download = True
                    log += u'Plex에 없음'
            item.log += u'16.Plex - %s : %s\n' % (log, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 17. option_min_size, option_max_size
    @staticmethod
    def check_option_size(item):
        try:
            flag_download = True
            option_min_size = ModelSetting.get_int('option_min_size')
            option_max_size = ModelSetting.get_int('option_max_size')
            if option_min_size != 0 and item.total_size < option_min_size:
                flag_download = False
                item.log += u'17.최소크기 - %s : %s\n' % (item.total_size, flag_download)
            if option_max_size != 0 and item.total_size > option_max_size:
                flag_download = False
                item.log += u'17.최대크기 - %s : %s\n' % (item.total_size, flag_download)
            if flag_download:
                item.log += u'17.크기 - %s : %s\n' % (item.total_size, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 15. option_sub
    @staticmethod
    def check_option_sub(item):
        try:
            log = item.movie_target
            flag_download = True
            value = ModelSetting.get('option_sub')
            if value == '0' or item.movie_target is None or item.movie_target in ['kor', 'kor_vod', 'vod']:
                flag_download = True
            elif value == '1':
                flag_download = False
                if item.sub:
                    flag_download = True
                    log += u' %s개' % len(item.sub)
            item.log += u'15.자막 - %s : %s\n' % (log, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 14. option_audio_codec
    @staticmethod
    def check_option_audio_codec(item):
        try:
            flag_download = False
            value = ModelSetting.get_list('option_audio_codec')
            log = ''
            if value is None or item.guessit is None or 'audio_codec' not in item.guessit:
                flag_download = True
            else:
                log = item.guessit['audio_codec']
                if item.guessit['audio_codec'] in value:
                    flag_download = True
            item.log += u'14.오디오 코덱 - %s : %s\n' % (log, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 13. option_video_codec
    @staticmethod
    def check_option_video_codec(item):
        try:
            flag_download = False
            value = ModelSetting.get_list('option_video_codec')
            log = ''
            if value is None or item.guessit is None or 'video_codec' not in item.guessit:
                flag_download = True
            else:
                log = item.guessit['video_codec']
                if item.guessit['video_codec'] in value:
                    flag_download = True
            item.log += u'13.비디오 코덱 - %s : %s\n' % (log, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 12. option_source
    @staticmethod
    def check_option_source(item):
        try:
            flag_download = False
            value = ModelSetting.get_list('option_source')
            log = ''
            if value is None or item.guessit is None or 'source' not in item.guessit:
                flag_download = True
            else:
                log = item.guessit['source']
                if item.guessit['source'] in value:
                    flag_download = True
            item.log += u'12.소스 - %s : %s\n' % (log, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download


    # 11. option_quality
    @staticmethod
    def check_option_quality(item):
        try:
            flag_download = False
            value = ModelSetting.get_list('option_quality')
            log = ''
            if value is None or item.guessit is None or 'screen_size' not in item.guessit:
                flag_download = True
            else:
                log = item.guessit['screen_size']
                if item.guessit['screen_size'] in value:
                    flag_download = True
            item.log += u'11.화질 - %s : %s\n' % (log, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 10. option_keyword_exclude
    @staticmethod
    def check_option_keyword_exclude(item):
        try:
            flag_download = True
            value = ModelSetting.get_list('option_keyword_exclude')
            match = ''
            if value is None:
                flag_download = True
            else:
                for v in value:
                    if item.filename.find(v) != -1:
                        flag_download = False
                        match = v
                        break
            item.log += u'10.제외 키워드 - %s : %s\n' % (match, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 9. option_keyword_include
    @staticmethod
    def check_option_keyword_include(item):
        try:
            flag_download = False
            value = ModelSetting.get_list('option_keyword_include')
            match = ''
            if value is None:
                flag_download = True
            else:
                for v in value:
                    if item.filename.find(v) != -1:
                        flag_download = True
                        match = v
                        break
            item.log += u'9.포함 키워드 - %s : %s\n' % (match, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download


    # 8. option_genre_exclude
    @staticmethod
    def check_option_rate(item):
        try:
            flag_download = True
            value = ModelSetting.get_list('option_rate')
            if value is None or item.daum_rate is None:
                flag_download = True
            else:
                if item.daum_rate in value:
                    flag_download = False
            item.log += u'8.등급 - %s : %s\n' % (item.daum_rate, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 7. option_genre_exclude
    @staticmethod
    def check_option_genre_exclude(item):
        try:
            flag_download = True
            value = ModelSetting.get_list('option_genre_exclude')
            if value is None or item.daum_genre is None:
                flag_download = True
            else:
                if item.daum_genre in value:
                    flag_download = False
            item.log += u'7.제외 장르 - %s : %s\n' % (item.daum_genre, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 6. option_genre_include
    @staticmethod
    def check_option_genre_include(item):
        try:
            flag_download = False
            value = ModelSetting.get_list('option_genre_include')
            if value is None or item.daum_genre is None:
                flag_download = True
            else:
                if item.daum_genre in value:
                    flag_download = True
            item.log += u'6.포함 장르 - %s : %s\n' % (item.daum_genre, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 5. option_year
    @staticmethod
    def check_option_year(item):
        try:
            flag_download = False
            value = ModelSetting.get_int('option_year')
            if value == '' or item.movie_year is None:
                flag_download = True
            else:
                if item.movie_year >= value:
                    flag_download = True
            item.log += u'5.년도 - %s : %s\n' % (item.movie_year, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 4. option_country_exclude
    @staticmethod
    def check_option_country_exclude(item):
        try:
            flag_download = True
            value = ModelSetting.get_list('option_country_exclude')
            if value is None or item.daum_country is None:
                flag_download = True
            else:
                if item.daum_country in value:
                    flag_download = False
            item.log += u'4.제외 국가 - %s : %s\n' % (item.daum_country, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 3. option_country_include
    @staticmethod
    def check_option_country_include(item):
        try:
            flag_download = False
            value = ModelSetting.get_list('option_country_include')
            if value is None or item.daum_country is None:
                flag_download = True
            else:
                if item.daum_country in value:
                    flag_download = True
            item.log += u'3.포함 국가 - %s : %s\n' % (item.daum_country, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 2. target
    @staticmethod
    def check_option_target(item):
        try:
            flag_download = False
            option_target = ModelSetting.get_list('option_target')
            if option_target is None or item.movie_target is None:
                flag_download = True
            else:
                if item.movie_target in option_target:
                    flag_download = True
            item.log += u'2.Target - %s : %s\n' % (item.movie_target, flag_download)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    # 1. 메타
    @staticmethod
    def check_option_meta(item):
        try:
            flag_download = False
            option_meta = ModelSetting.get('option_meta')
            if option_meta == '0':
                flag_download = True
            elif option_meta == '1':
                if item.movie_title is not None and item.daum_poster is not None:
                    flag_download = True
            elif option_meta == '2':
                if item.movie_title is not None:
                    flag_download = True
            item.log += u'1.메타 : %s\n' % flag_download
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    

# -*- coding: utf-8 -*-
#########################################################
# python
import traceback
from datetime import datetime
import json
import os

# third-party
from sqlalchemy import or_, and_, func, not_, desc
from sqlalchemy.orm import backref

# sjva 공용
from framework import app, db, path_app_root
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from downloader import ModelDownloaderItem

app.config['SQLALCHEMY_BINDS'][package_name] = 'sqlite:///%s' % (os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name))
#########################################################
        
class ModelSetting(db.Model):
    __tablename__ = '%s_setting' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)
 
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        return {x.name: getattr(self, x.name) for x in self.__table__.columns}

    @staticmethod
    def get(key):
        try:
            return db.session.query(ModelSetting).filter_by(key=key).first().value.strip()
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
            
    
    @staticmethod
    def get_int(key):
        try:
            return int(ModelSetting.get(key))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def get_bool(key):
        try:
            return (ModelSetting.get(key) == 'True')
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def set(key, value):
        try:
            item = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
            if item is not None:
                item.value = value.strip()
                db.session.commit()
            else:
                db.session.add(ModelSetting(key, value.strip()))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def to_dict():
        try:
            from framework.util import Util
            return Util.db_list_to_dict(db.session.query(ModelSetting).all())
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())


    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                if key in ['scheduler', 'is_running']:
                    continue
                logger.debug('Key:%s Value:%s', key, value)
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True                  
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            logger.debug('Error Key:%s Value:%s', key, value)
            return False

    @staticmethod
    def get_list(key):
        try:
            value = ModelSetting.get(key)
            values = [x.strip().replace(' ', '').strip() for x in value.replace('\n', '|').split('|')]
            values = Util.get_list_except_empty(values)
            return values
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            logger.error('Error Key:%s Value:%s', key, value)


class ModelMovieItem(db.Model):
    __tablename__ = '%s_item' % package_name 
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)

    # 수신받은 데이터 전체
    data = db.Column(db.JSON)

    # 자막
    sub = db.Column(db.JSON)

    # 토렌트 정보
    name = db.Column(db.String)
    filename = db.Column(db.String)
    dirname = db.Column(db.String)
    magnet = db.Column(db.String)
    file_count = db.Column(db.Integer)
    total_size = db.Column(db.Integer)
    url = db.Column(db.String)
    # guessit
    guessit = db.Column(db.JSON)

    # 메타
    movie_title = db.Column(db.String)
    movie_target = db.Column(db.String)
    movie_id = db.Column(db.String)
    movie_kor = db.Column(db.Boolean)
    movie_year = db.Column(db.Integer)
    
    daum_poster = db.Column(db.String)
    daum_country = db.Column(db.String)
    daum_eng_title = db.Column(db.String)
    daum_rate = db.Column(db.String)
    daum_genre = db.Column(db.String)

    # 다운로드 정보
    download_status = db.Column(db.String)
    plex_key = db.Column(db.String)
    
    downloader_item_id = db.Column(db.Integer, db.ForeignKey('plugin_downloader_item.id'))
    downloader_item = db.relationship('ModelDownloaderItem')

    download_check_time = db.Column(db.DateTime)
    log = db.Column(db.String)

    plex_info = db.Column(db.JSON)
    
    # 2 버전 추가
    server_id = db.Column(db.Integer)

    # 2 버전 추가
    folderid = db.Column(db.String)
    folderid_time = db.Column(db.DateTime)
    share_copy_time = db.Column(db.DateTime)
    share_copy_complete_time = db.Column(db.DateTime)

    def __init__(self):
        self.created_time = datetime.now()
        self.download_status = ''
        
    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') 
        ret['download_check_time'] = self.download_check_time.strftime('%m-%d %H:%M:%S') if self.download_check_time is not None  else None
        ret['downloader_item'] = self.downloader_item.as_dict() if self.downloader_item is not None else None
        ret['folderid_time'] = self.folderid_time.strftime('%m-%d %H:%M:%S') if self.folderid_time is not None  else None
        ret['share_copy_time'] = self.share_copy_time.strftime('%m-%d %H:%M:%S') if self.share_copy_time is not None  else None
        ret['share_copy_complete_time'] = self.share_copy_complete_time.strftime('%m-%d %H:%M:%S') if self.share_copy_complete_time is not None  else None
        return ret
    
    
    @staticmethod
    def process_telegram_data(data):
        try:
            magnet = 'magnet:?xt=urn:btih:' + data['t']['hash']
            entity = db.session.query(ModelMovieItem).filter_by(magnet=magnet).first()
            
            if entity is not None:
                if 's' not in data: # 새로받은게 자막이 없다면
                    return
                if entity.sub is not None: # 새로받은게 자막이 있지만, 기존것도 자막이 있다면
                    return
                    
            entity =  ModelMovieItem()
            entity.server_id = data['server_id']
            entity.data = data

            entity.name = data['t']['name']
            entity.total_size = data['t']['size']
            entity.file_count = data['t']['num']
            entity.magnet = magnet
            entity.filename = data['t']['filename']
            entity.dirname = data['t']['dirname']
            entity.url = data['t']['url']

            from guessit import guessit
            entity.guessit = guessit(entity.filename)
            for key, value in entity.guessit.items():
                entity.guessit[key] = str(value)
            """
            if 'language' in entity.guessit:
                entity.guessit['language'] = str(entity.guessit['language'])
            if 'subtitle_language' in entity.guessit:
                entity.guessit['subtitle_language'] = str(entity.guessit['subtitle_language'])
            if 'audio_bit_rate' in entity.guessit:
                entity.guessit['audio_bit_rate'] = str(entity.guessit['audio_bit_rate'])
            if 'size' in entity.guessit:
                entity.guessit['size'] = str(entity.guessit['size'])
            if 'country' in entity.guessit:
                entity.guessit['country'] = str(entity.guessit['country'])
            """
            
            if 'm' in data:
                entity.movie_title = data['m']['title']
                entity.movie_target = data['m']['target']
                entity.movie_kor = data['m']['kor']
                entity.movie_year = data['m']['year']
                entity.movie_id = data['m']['id']
                if entity.movie_target != 'imdb':
                    entity.daum_country = data['m']['daum']['country']
                    entity.daum_poster = data['m']['daum']['poster']
                    entity.daum_eng_title = data['m']['daum']['eng']
                    entity.daum_rate = data['m']['daum']['rate']
                    entity.daum_genre = data['m']['daum']['genre']
            if 's' in data:
                entity.sub = data['s']

            if entity.movie_target is not None and entity.movie_target != 'imdb':
                entity.plex_info = ModelMovieItem.get_plex_info(entity.movie_title, entity.movie_id)

            db.session.add(entity)
            db.session.commit()
            return entity
        except Exception as e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())   


    @staticmethod
    def get_plex_info(title, daum_id):
        logger.debug('get_plex_info : %s %s', title, daum_id)
        try:
            ret = []
            import plex
            plex_videos = plex.Logic.library_search_movie(title, daum_id)

            if plex_videos:
                for v in plex_videos:
                    entity = {}
                    entity['key'] = v.key
                    entity['exist_smi'] = False
                    entity['exist_srt'] = False
                    sub_list = v.subtitleStreams()
                    for sub in sub_list:
                        if sub.format == 'srt':
                            entity['exist_srt'] = True
                        elif sub.format == 'smi':
                            entity['exist_smi'] = True
                    entity['media'] = []
                    for m in v.media:
                        tmp = '%s / %s / %s / %s' % (m.videoResolution, m.videoCodec, m.audioCodec, m.videoFrameRate)
                        entity['media'].append({'info':tmp, 'file':m.parts[0].file})
                    ret.append(entity)
            return ret
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    

    @staticmethod
    def web_list(req):
        try:
            ret = {}
            page = 1
            page_size = ModelSetting.get_int('web_page_size')
            job_id = ''
            search = ''
            if 'page' in req.form:
                page = int(req.form['page'])
            if 'search_word' in req.form:
                search = req.form['search_word']
            option = req.form['option']
            order = req.form['order'] if 'order' in req.form else 'desc'

            query = ModelMovieItem.make_query(search=search, option=option, order=order)
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            logger.debug('ModelMovieItem count:%s', count)
            lists = query.all()
            ret['list'] = [item.as_dict() for item in lists]
            ret['paging'] = Util.get_paging_info(count, page, page_size)
            return ret
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def api_list(req):
        try:
            option = req.args.get('option')
            search = req.args.get('search')
            count = req.args.get('count')
            if count is None or count == '':
                count = 100
            server_id_mod = req.args.get('server_id_mod')
            query = ModelMovieItem.make_query(option=option, search=search, server_id_mod=server_id_mod)
            query = (query.order_by(desc(ModelMovieItem.id))
                .limit(count)
            )
            lists = query.all()
            return lists
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def make_query(search='', option='all', order='desc', server_id_mod=None):
        query = db.session.query(ModelMovieItem)
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(ModelMovieItem.filename.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(ModelMovieItem.filename.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(or_(ModelMovieItem.filename.like('%'+search+'%'), ModelMovieItem.movie_title.like('%'+search+'%')))

        
        if option == 'wait':
            query = query.filter(ModelMovieItem.download_status == '')
        elif option == 'true':
            query = query.filter(ModelMovieItem.download_status.like('true%'), not_(ModelMovieItem.download_status.like('true_only_status%')))
        elif option == 'false':
            query = query.filter(ModelMovieItem.download_status.like('false%'), not_(ModelMovieItem.download_status.like('false_only_status%')))
        elif option == 'true_only_status':
            query = query.filter(ModelMovieItem.download_status.like('true_only_status%'))
        elif option == 'false_only_status':
            query = query.filter(ModelMovieItem.download_status.like('false_only_status%'))
        elif option == 'no':
            query = query.filter(ModelMovieItem.download_status.like('no%'))

        if order == 'desc':
            query = query.order_by(desc(ModelMovieItem.id))
        else:
            query = query.order_by(ModelMovieItem.id)

        if server_id_mod is not None and server_id_mod != '':
            tmp = server_id_mod.split('_')
            if len(tmp) == 2:
                query = query.filter(ModelBotDownloaderKtvItem.server_id % int(tmp[0]) == int(tmp[1]))

        return query

    @staticmethod
    def remove(id):
        try:
            entity = db.session.query(ModelMovieItem).filter_by(id=id).first()
            if entity is not None:
                db.session.delete(entity)
                db.session.commit()
                return True
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
    
    @staticmethod
    def get_by_id(id):
        try:
            return db.session.query(ModelMovieItem).filter_by(id=id).first()
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def receive_share_data(data):
        try:
            query = db.session.query(ModelMovieItem).filter(ModelMovieItem.server_id == int(data['server_id']))
            query = query.filter(ModelMovieItem.magnet.like('%'+ data['magnet_hash']))
            entity = query.with_for_update().first()
            
            if entity is not None:
                #logger.debug(entity)
                entity.folderid = data['folderid']
                entity.folderid_time = datetime.now()
                db.session.commit()
                from .logic_normal import LogicNormal
                LogicNormal.process_gd(entity)
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
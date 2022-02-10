import gitlab
import sys
import logging
from logger_init import logger_init
import yaml
import time


lg = logger_init()
logger = logging.getLogger("Train")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.info("Train start")
try:
    with open("./config/train.yml", "r") as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
except FileNotFoundError:
    logger.error("Can't find config file in: train.yml ")
    sys.exit(1)


class GL_CALL():
    def __init__(self, prj_num, url=cfg.get('url'), token=cfg.get('token')):
        try:
            self.gl = gitlab.Gitlab(url, private_token=token)
            self.gl.auth()
            self.project = self.gl.projects.get(prj_num)
            logger.debug("Init Class Train in project")
        except Exception as ff:
            logger.info("No connect to Gitlab")
            logger.debug(ff)
            pass
        # finally:
        #     logger.info("No connect to Gitlab")
        #     startTrain()

    def get_mrs(self):
        self.mrq = self.project.mergerequests.list(
            scope="all",
            state=cfg.get('state'),
            order_by=cfg.get('order_by'),
            sort=cfg.get('sort'),
            per_page=cfg.get('limit')
            )
        self.mrs_r = self.mrq[::-1]
        logger.debug("get_mrs", extra={'train': {'mrs': self.mrs_r}})
        return self.mrs_r

    def get_mr(self, id):
        self.mr_id = id.iid
        self.mr_info = self.project.mergerequests.get(self.mr_id, include_rebase_in_progress=True)
        logger.debug("get_mr", extra={
            'train': {
                'mr id': self.mr_id,
                'mr info': self.mr_info
                    }
                }
            )
        return self.mr_info

    def get_approved(self):
        self.check_approve = self.mr_info.approvals.get()
        if cfg.get('approved') is True:
            if self.check_approve.approved is True:
                return True
            else:
                return False
        else:
            return True

    def get_last_pipeline(self):
        self.pipline_info = self.mr_info.pipelines.list()[0]
        logger.debug("get_last_pipeline", extra={
            'train': {
                'last pipeline': self.pipline_info
                    }
                }
            )
        return self.pipline_info

    def run_manual_jobs(self):
        self.pipeline = self.project.pipelines.get(self.pipline_info.id)
        self.pipeline_jobs = self.pipeline.jobs.list(per_page=cfg.get('job_per_req'))
        logger.debug(f"list jobs: {self.pipeline_jobs}")
        self.num_jobs = 0
        for i in self.pipeline_jobs:
            self.job = self.project.jobs.get(i.id, lazy=False)
            self._job_log_ = {
                'train': {
                    'pipelien id': self.pipline_info.id,
                    'job id': self.job.id, 
                    'job status': self.job.status
                    }
                }
            if self.job.status == "manual":
                self.num_jobs += 1
                try:
                    self.job.play()
                    logger.info("Job started", extra=self._job_log_)
                except Exception as ff:
                    logger.exception(ff)
                    continue
        return self.num_jobs

    # def run_pipline(self):
        # print("start GETTER")
        # self.pipeline = self.project.pipelines.get(self.pipline_info.id)
        # self.pip_jobs = self.pipeline.jobs.list()
        # print(self.pip_jobs)
        # for i in self.pip_jobs:
            # self.job = self.project.jobs.get(i.id, lazy=False)
            # if self.job.status == "manual":
                # self.job.play()
            # self.job.play()
        # self.pipeline_run = self.project.pipelines.create({'ref': self.pipline_info.ref, 'variables': [{'key': 'PIPELINE_TRIGER', 'value': 'true'}]})
        # print(self.pipeline)
        # print("stop GETTER")
        # return True

    def set_rebase(self):
        self._mr_log_ = {'train': {'mr id': self.mr_id, 'pipelien id': self.pipline_info.id}}
        try:
            if cfg.get('rebase') is True:
                # return dict {'rebase_in_progress': 'true'} always
                # self.rebase = self.mr_info.rebase()
                logger.info("Push Rebase", extra=self._mr_log_)
                self.set_note("Train: push Rebase")
            else:
                self.set_note("Train: Rebase is disabled in config")
                logger.info("Disable Rebase", extra=self._mr_log_)
        except Exception as ff:
            logger.exception(ff)

    def set_mr_apply(self):
        self._mr_log_ = {'train': {'mr id': self.mr_id, 'pipelien id': self.pipline_info.id}}
        try:
            if cfg.get("merge") is True:
                # return nothing
                self.mr_apply = self.mr_info.merge(merge_when_pipeline_succeeds=True)
                logger.info("Push Merge", extra=self._mr_log_)
                self.set_note("Train: push Merge")
            else:
                self.set_note("Train: Merge is disabled in config")
                logger.info("Disable Merge", extra=self._mr_log_)
        except Exception as ff:
            logger.exception(ff)

    def get_note_mr_approve(self):
        if cfg.get('note_mr_approved') is not None: 
            self.notes_list = self.mr_info.notes.list()
            for ni in self.mr_info.notes.list():
                self.note = self.mr_info.notes.get(ni.id)
                if str(self.note.body).lower() == str(cfg.get('note_mr_approved')).lower():
                    logger.debug("Check notes: Note Pass")
                    return True
                else:
                    continue
            logger.debug("Check notes: Note failed")
            return False
        logger.debug("Check notes: Disable")
        return True

    def set_note(self, message):
        self._msg = message
        if self._check_notes_(self._msg) is True:
            self.mr_note = self.mr_info.notes.create({'body': self._msg})

    def _check_notes_(self, message):
        self._msg_ = message
        for ni in self.mr_info.notes.list():
            self.note = self.mr_info.notes.get(ni.id)
            if str(self.note.body) == str(self._msg_):
                logger.debug("Check notes: Note is duplicate")
                return False
            else:
                continue
        logger.debug("Check notes: Note is ok")
        return True


class GL_PROC():
    def __init__(self, prj_num):
        self.prj_num = prj_num
        self.prj = GL_CALL(self.prj_num)
        self.mr_num = 0

    def check_mr(self):
        for self.mr in self.prj.get_mrs():
            self.mr_num += 1
            self.mr_info = self.prj.get_mr(self.mr)
            self.check_loop = False
            logger.debug(self.mr_info)
            self._mr_log_ = {
                'train': {
                    'merge req id': self.mr.iid,
                    'merge status': self.mr_info.merge_status,
                    'merge error': self.mr_info.merge_error
                    }
                }
            if self.mr_info.work_in_progress is True or self.mr_info.draft is True:
                logger.info("MR DROP: Draft",
                            extra=self._mr_log_)
                continue
            elif self.prj.get_note_mr_approve() is False:
                logger.info(f"MR DROP: Not found Keyword - {cfg.get('note_mr_approved')}",
                            extra=self._mr_log_)
                continue
            elif self.prj.get_approved() is False:
                logger.info("MR DROP: not approved", extra=self._mr_log_)
                self.prj.set_note("Train: MR isn't approved")
                continue
            elif self.mr_info.merge_status == 'checking':
                logger.info("TRAIN STOP: We are waiting for the correct states from the server",
                            extra=self._mr_log_)
                self.check_loop = False
                break
            elif self.mr_info.merge_status != 'can_be_merged' or self.mr_info.merge_error is not None:
                logger.warning("MR DROP: Problem to Merge",
                               extra=self._mr_log_)
                self.prj.set_note(f"Train: Skiped, I can't do the merge.  \n\
                                  Merge Status: {self.mr_info.merge_status}  \n\
                                  Merge Error : {self.mr_info.merge_error}")
                continue
            else:
                logger.info("MR suitable: gonna processing pipeline",
                            extra=self._mr_log_)
                self.check_loop = True
                break
        return self.check_loop

    def get_mr_num(self):
        return self.mr_num

    def check_pipeline(self):
        self.pipeline = self.prj.get_last_pipeline()
        self._pipline_log_ = {
            'train': {
                'merge req id': self.mr.iid,
                'pipeline id': self.pipeline.id,
                'pipline_status': self.pipeline.status
                }
            }
        if self.pipeline.status == 'success':
            logger.info("Pipeline Success", extra=self._pipline_log_)
            self.prj.set_rebase()
            self.prj.set_mr_apply()
        elif self.pipeline.status == 'manual':
            logger.info("Pipeline Manual", extra=self._pipline_log_)
            self.prj.set_rebase()
            self.num = self.prj.run_manual_jobs()
            logger.info(f"{self.num} Jobs have been started", extra=self._pipline_log_)
            self.prj.set_note(f"Train: started {self.num} jobs in the last pipeline")
        elif self.pipeline.status == 'running':
            logger.info("Pipeline Running", extra=self._pipline_log_)
            # self.prj.set_rebase()      # i am not sure that we need it here
        else:
            logger.error("Pipeline Unknown", extra=self._pipline_log_)


def startTrain():
    for i in cfg.get('projects'):
        logger.info(f"Project ID: {i}")
        prj = GL_PROC(i)
        mr = prj.check_mr()
        if mr is True:
            prj.check_pipeline()
        logger.info(f"FINISH: Total processed MR: {prj.get_mr_num()} in project: {i}")

def reloadConfig():
    global cfg
    try:
        with open("./config/train.yml", "r") as ymlfile:
            cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    except FileNotFoundError:
        logger.error("Can't find config file in: train.yml ")
        sys.exit(1)


if __name__ == '__main__':
    while True:
        reloadConfig()
        startTrain()
        logger.info(f"Sleep: {cfg.get('interval')} sec")
        time.sleep(cfg.get('interval'))

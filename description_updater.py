import requests
import tomli
from typing import Iterator, List, Dict
from dataclasses import dataclass, field
from dotenv import load_dotenv
import os
from datetime import datetime
import time
import logging

logging.basicConfig(filename='logs.log',
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)


class Logger216:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        fh = logging.FileHandler('logs.log')
        self.logger.addHandler(fh)

    def info(self, message):
        self.logger.info(message)

    def debug(self, message):
        self.logger.debug(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)


logger = Logger216()

logger.info("Loading .env file...")
load_dotenv('.env')

logger.info("Loading api key file...")
API_KEY = os.getenv('MAINTENENCE_216_API_KEY')

logger.info("Loading params.toml file...")
with open("params.toml", "rb") as f:
    config = tomli.load(f)


class ClickUpSettings:
    _CLICKUP_PERSONAL_API_KEY: str = API_KEY  # TODO: Swap API KEY when ready to test for 216.
    CLICKUP_ACTIVE_USER: Dict = field(init=False)
    CLICKUP_TEAM_NAME: str = config["CLICKUP-216-TEAM-NAME"]  # TODO: Create constant for this in toml file.
    CLICKUP_TEAM_ID: str = config['CLICKUP-216-TEAM-ID']  # TODO: Create constant for this in toml file.
    CLICKUP_TEAM_SPACES: List[str] = config[
        'CLICKUP-216-SPACE-NAMES']  # TODO: MIGHT create a constant for this in toml file.
    CLICKUP_FOLDER_IDS: Dict = config['CLICKUP-216-JOSH-TASK-FOLDER-ID']
    CLICKUP_LIST_IDS: Dict = field(init=False)
    CLICKUP_JOSH_TASK_FOLDER_NAME = config['CLICKUP-216-JOSH-TASK-FOLDER-NAME']
    CLICKUP_DISPATCH_LIST_NAME = config['CLICKUP-216-DISPATCH-LIST-NAME']
    CLICKUP_DISPATCH_LIST_ID = config['CLICKUP-216-DISPATCH-LIST-ID']
    CLICKUP_DISPATCH_DICT = {CLICKUP_JOSH_TASK_FOLDER_NAME: {CLICKUP_DISPATCH_LIST_NAME: CLICKUP_DISPATCH_LIST_ID}}
    TASK_SUBJECT_CHANGES = config['TEXT-TO-REMOVE-FROM-DESC']['SUBJECTS-TO-REMOVE']
    TASK_HEADER_CHANGES = config['TEXT-TO-REMOVE-FROM-DESC']['HEADERS-TO-REMOVE']
    TASK_FOOTER_CHANGES = config['TEXT-TO-REMOVE-FROM-DESC']['FOOTERS-TO-REMOVE']


@dataclass
class WorkSpaceGetter:
    task_list: dict = field(init=False)
    __api_key: str = ClickUpSettings._CLICKUP_PERSONAL_API_KEY
    _settings: ClickUpSettings = ClickUpSettings()

    def __post_init__(self):
        ClickUpSettings.CLICKUP_TEAM_ID = [
            x for x in self.team_getter()['teams'] if x['name'] == ClickUpSettings.CLICKUP_TEAM_NAME][0]['id']

        ClickUpSettings.CLICKUP_TEAM_SPACES = [
            x['id'] for x in self.workspace_getter(
                team_id=ClickUpSettings.CLICKUP_TEAM_ID)['spaces'] if x['name'] in config['CLICKUP-216-SPACE-NAMES']
        ]

        ClickUpSettings.CLICKUP_FOLDER_IDS = self.get_folder_ids()

        ClickUpSettings.CLICKUP_LIST_IDS = self.list_getter

    def get_myuser(self, team_id: str = ClickUpSettings.CLICKUP_TEAM_ID):
        logger.info("Getting active user...")
        url = "https://api.clickup.com/api/v2/user"

        _headers = {"Authorization": self.__api_key}

        data = self.get_response(_url=url, _headers=_headers)
        ClickUpSettings.CLICKUP_ACTIVE_USER = data['user']

    def get_folder_ids(self):
        logger.info("Getting folder ids...")
        folders = [x['folders'] for x in self.folder_getter(space_id=ClickUpSettings.CLICKUP_TEAM_SPACES)]

        logger.info("Got folder ids.")
        return {x['name']: x['id'] for x in folders for x in x}

    @staticmethod
    def get_response(_url: str, _headers: dict, **kwargs) -> requests.Response:
        """
        :param _url: The URL to send the request to.
        :param _headers: The headers to send with the request.
        :param kwargs: The parameters to send with the request.
        :return: The response from the request in JSON format.
        """
        logger.info(f"Sending request to {_url}")
        response = requests.get(_url, headers=_headers, params=kwargs.get('_params', None))
        return response.json()

    def team_getter(self):
        """
        Get Team ID for ClickUp Team.
        :return: The response from the request in JSON format.
        """
        _url = config['CLICKUP-TEAM-URL']

        _headers = {"Authorization": self.__api_key}
        return self.get_response(_url, _headers=_headers)

    def workspace_getter(self, team_id: str = ClickUpSettings.CLICKUP_TEAM_ID) -> requests.Response:
        """
        Get Workspace ID for ClickUp Team Workspace.
        :return:
        """
        _url = config['CLICKUP-TEAM-URL'] + team_id + "/space"

        _query = {
            "archived": "false"
        }

        _headers = {"Authorization": self.__api_key}

        return self.get_response(_url, _headers=_headers, _params=_query)

    def folder_getter(self, space_id: ClickUpSettings.CLICKUP_TEAM_SPACES) -> Iterator[requests.Response]:
        """
        Get List of Folders in Team's Space
        :param space_id: The ID of the space to get the folders from.
        :return: Generator object of the folders in each space.
        """
        for each_id in space_id:
            _url = config['CLICKUP-SPACE-URL'] + each_id + "/folder"

            _query = {
                "archived": "false"
            }

            _headers = {"Authorization": self.__api_key}

            yield self.get_response(_url, _headers=_headers, _params=_query)

    def _list_id_getter(self, folder_id: dict) -> Iterator[requests.Response]:
        for k, v in folder_id.items():
            url = config['CLICKUP-FOLDER-URL'] + v + "/list"

            query = {
                "archived": "false"
            }

            headers = {"Authorization": self.__api_key}
            yield {k: self.get_response(url, _headers=headers, _params=query)}

    def list_getter(self):
        folder_dict = {}
        for x in self._list_id_getter(ClickUpSettings.CLICKUP_FOLDER_IDS):
            list_dictionary = {}
            for k, v in x.items():
                for y in v['lists']:
                    list_dictionary.update({y['name']: y['id']})
            folder_dict.update({k: list_dictionary})
        return folder_dict

    def task_list_getter(self):
        task_ids = ClickUpSettings.CLICKUP_DISPATCH_DICT
        task_list = {}
        for k, v in task_ids.items():
            task_details = {}
            for x, y in v.items():
                url = config['CLICKUP-LIST-URL'] + y + "/task"

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": self.__api_key
                }
                try:
                    task_details.update({x: self.get_response(url, _headers=headers)['tasks']})
                except ValueError:
                    pass

            task_list.update({k: task_details})
            self.task_list = task_list
        return self.task_list


@dataclass
class TaskEditor:
    task: Dict
    updated_task: Dict = field(init=False)
    response: requests.Response = field(init=False)

    def __post_init__(self):
        ...

    @staticmethod
    def replace_text(text: str, changes: list) -> str:
        for change in changes:
            text = text.replace(change, "")

        split = text.splitlines()
        for line in split:
            if line in changes:
                split.remove(line)
        return ' '.join([line.strip() for line in split]).strip()

    def edit_task(self):
        logger.info(f"Reading task: {self.task['name'], self.task['id']}")
        self.updated_task = self.task.copy()
        # self.updated_task['priority'] = int(self.updated_task['priority']['id'])
        # self.updated_task['name'] = self.replace_text(self.updated_task['name'], ClickUpSettings.TASK_SUBJECT_CHANGES)
        for subject in ClickUpSettings.TASK_SUBJECT_CHANGES:
            if subject in self.updated_task['name']:
                self.updated_task['name'] = self.updated_task['name'].replace(subject, "")
                logger.info(f"Updated {subject} task name.")
        for each in ['description', 'text_content']:
            self.updated_task[each] = self.replace_text(self.updated_task[each], ClickUpSettings.TASK_HEADER_CHANGES)
            self.updated_task[each] = self.replace_text(self.updated_task[each], ClickUpSettings.TASK_FOOTER_CHANGES)
            logger.info(f"Updated {each} task and description.")
        return self.updated_task

    def post_comment(self, comment: str = None):
        task_id: str = self.updated_task['id']
        if not comment:
            comment = "This task has been updated by the ClickUp Bot."
        url = config['CLICKUP-TASK-URL'] + task_id + "/comment"
        payload = {
            "comment_text": comment,
            "assignee": None,
            "notify_all": False
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": ClickUpSettings._CLICKUP_PERSONAL_API_KEY
        }
        logger.info(f"Posting comment to task...Name: {self.task['name'], self.task['id']}")
        response = requests.post(url, json=payload, headers=headers)
        logger.info(f"Comment posted to task...Name: {self.task['name'], self.task['id']}")

        data = response.json()
        print(data)

        return comment

    def put_update(self, task: Dict):
        task_id: str = task['id']
        url = config['CLICKUP-TASK-URL'] + task_id

        headers = {
            "Content-Type": "application/json",
            "Authorization": ClickUpSettings._CLICKUP_PERSONAL_API_KEY
        }

        payload = {"name": task['name'],
                   "description": task['description'],
                   "text_content": task['text_content'], }
        try:
            response = requests.put(url, json=payload, headers=headers)
        except requests.exceptions.JSONDecodeError as e:
            print('===================== ERROR =====================')
            print(e)
            print('===================== TASK WITH ERROR =====================')
            print(task)
            raise e

        logger.info(f"Task updated...Name: {self.task['name'], self.task['id']}")
        self.response = response.json()
        return self.response


@dataclass
class TaskRunner:
    logger.info("Checked for updated tasks at " + str(datetime.now()))
    workspace = WorkSpaceGetter()
    last_update_time = 0

    def __post_init__(self):
        self.workspace.get_myuser()

        self.task_list = self.workspace.task_list_getter()
        self.josh_tasks = self.task_list[
            ClickUpSettings.CLICKUP_JOSH_TASK_FOLDER_NAME][ClickUpSettings.CLICKUP_DISPATCH_LIST_NAME]

    def run(self):
        for _ in range(250):
            logger.info("Checked for updated tasks at " + str(datetime.now()))
            for x in self.josh_tasks:
                task = TaskEditor(x)
                task.edit_task()
                if int(task.updated_task['date_created']) >= TaskRunner.last_update_time:
                    if not task.updated_task == task.task:
                            task.put_update(task.updated_task)
                            task.post_comment()
                    else:
                        logger.info(f"Task update not needed for task {task.task['name'], task.task['id']}")

                    TaskRunner.last_update_time = task.task['date_created']
                    logger.info(f"Last update time changed to {TaskRunner.last_update_time}")

            time.sleep(300)


runner = TaskRunner()
runner.run()
#
# test = task_loop[0]
#
#
#
# edited_test = test.edit_task()

# print('\n=========== Original TASK =========== \n')
# pp(test.task['description'])
#
# print('\n =========== UPDATED TASK =========== \n')
# pp(test.updated_task['description'])
# qr_tasks = task_list['Quorum Report']
# updated_tasks = []
# for l in qr_tasks:
#     for t in qr_tasks[l]:
#         task = TaskEditor(t)
#         updated_tasks.append(task.edit_description())

# all_tasks = {}
# for task in task_list:
#     task_details = {}
#     for k, v in task_list[task].items():
#         # print(v)
#         for x in v:
#             print(x)
#             task_details.update({k: {x['name']: v}})
#     all_tasks.update({task: task_details})
#
# # Get Clickup Team ID
# settings.CLICKUP_TEAM_ID = [
#     x for x in test.team_getter()['teams'] if x['name'] == settings.CLICKUP_TEAM_NAME][0]['id']
#
#
# # Get Clickup Team Space ID
# settings.CLICKUP_TEAM_SPACES = [
#     x['id'] for x in test.workspace_getter(
#         team_id=settings.CLICKUP_TEAM_ID)['spaces'] if x['name'] in config['CLICKUP-SPACE-NAMES']]
#
# # Get Clickup Team Folder IDs
# folders = [x['folders'] for x in test.folder_getter(space_id=settings.CLICKUP_TEAM_SPACES)]
# settings.CLICKUP_FOLDER_IDS = {x['name']: x['id'] for x in folders for x in x}

# folder_dict = {}
# for x in list_get:
#     list_dictionary = {}
#     for k, v in x.items():
#         for y in v['lists']:
#             list_dictionary.update({y['name']: y['id']})
#     folder_dict.update({k: list_dictionary})

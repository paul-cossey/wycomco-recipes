#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-

"""
Copyright 2022 bock@wycomco.de
Inspiration taken from and looseley based on JamfUploaderTeamsNotifier.py by
Graham Pugh, Jacob Burley

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import subprocess
from datetime import datetime
from time import sleep
from autopkglib import Processor, ProcessorError

__all__ = ["MunkiRepoTeamsSummarizer"]


class MunkiRepoTeamsSummarizer(Processor):
    description = (
        "Collects and optionally posts changes to Teams via webhook based on "
        "the output of a MunkiImporter or MunkiAutoStaging process."
        "Using a messages cache file is required for summarizing the output of"
        "multiple recipes in a single post."
    )
    input_variables = {
        "msg_file_path": {
            "required": False,
            "description": ("Local Teams messages file path. Messages will be "
                            "stored to file if present."),
            "default": "",
        },
        "msg_file_clear_at_start": {
            "required": False,
            "description": ("Wether to reset messages in /path/file.json when "
                "the processor starts."
                "Will be ignored if msg_file_path is not given."),
            "default": False,
        },
        "msg_file_clear_after_send": {
            "required": False,
            "description": ("Wether to reset messages in /path/file.json when "
                "messages were successfuly sent."
                "Will be ignored if msg_file_path is not given."),
            "default": True,
        },
        "msg_file_clear_at_finish": {
            "required": False,
            "description": ("Wether to reset messages in /path/file.json when "
                "messages were not send and the processor finishes."
                "Will be ignored if msg_file_path is not given."),
            "default": False,
        },
        "teams_webhook_url": {
            "required": False,
            "description": ("Teams webhook. If present sending a summarizing "
                "message will be attempted."),
            "default": "",
        },
        "teams_username": {
            "required": False,
            "description": ("Teams MessageCard display name."),
            "default": "AutoPkg",
        },
        "teams_icon_url": {
            "required": False,
            "description": ("Teams display icon URL."),
            "default": "https://munkibuilds.org/logo.jpg",
        },
        "munki_repo_changed": {
            "required": False,
            "description": (
                "Indicates if an item was imported by "
                "MunkiImporter or modified by MunkiAutoStaging."
            ),
            "default": False,
        },
        "munki_importer_summary_result": {
            "required": False,
            "description": (
                "The pkginfo property list. Empty if item was not " "imported."
            ),
        },
        "munki_autostaging_summary_result": {
            "required": False,
            "description": ("Result of the MunkiAutoStaging processor."),
        },
    }
    output_variables = {}

    __doc__ = description

    def _curl_json_poster(self, message_json, teams_webhook_url):
        """
        Sends a JSON formatted message via curl through a teams webhook.
        """
        # curl -H "Content-Type: application/json" -d "${JSON}" "${WEBHOOK_URL}"
        curl_cmd = [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail-with-body",
            "-H" "Content-Type: application/json",
            "-d",
            message_json,
            teams_webhook_url,
        ]
        try:
            proc = subprocess.Popen(
                curl_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            (out, err) = proc.communicate()
        except (IOError, OSError) as error:
            raise ProcessorError(error)
        if proc.returncode != 0 or err:
            raise ProcessorError(
                "curl returned an error while sending teams "
                "message via webhook.",
                f"returncode: {proc.returncode}",
                f"stdout: {out}",
                f"stderr: {err}",
            )
            self.output(
                "curl returned an error while sending teams message"
                "via webhook."
            )
            self.output(f"returncode: {proc.returncode}")
            self.output(f"stdout: {out}")
            self.output(f"stderr: {err}")
            return False
        return True

    def send_teams_message(self, teams_webhook_url, message):
        """
        Converts a Teams message-dictionary to a JSON formatted string and
        invokes _curl_json_poster to send it to teams.
        """
        message_json = json.dumps(message)
        for count in range(1, 6):
            self.output(
                "Teams webhook post attempt {}".format(count), verbose_level=2
            )
            success = self._curl_json_poster(message_json, teams_webhook_url)
            if success:
                break
            sleep(10)
        else:
            self.output("Giving up posting to Teams:")
            self.output("Teams webhook send did not succeed after 5 attempts")
            raise ProcessorError(
                "ERROR: Teams webhook failed to send 5 times."
            )

    def new_message(
        self,
        title="",
        activity_title="",
        activity_subtitle="",
        activity_image="",
    ):
        """
        Creates an empty Teams activity message dictionary. This empty
        dictionary is accepted when sent to teams.
        Optional parameters like titles can be set / changed through named
        methods of this module.
        """
        message = {
            "type": "message",
            "attachments": [
                {
                    "contentType":
                        "application/vnd.microsoft.teams.card.o365connector",
                    "content": {
                        "$schema": "https://schema.org/extensions",
                        "sections": [
                            {
                                # "activityImage":
                                # "https://munkibuilds.org/logo.jpg",
                                "activitySubtitle": activity_subtitle,
                                "activityTitle": activity_title,
                                "facts": [
                                    # {
                                    #     "name": "foo",
                                    #     "value": "bar"
                                    # }
                                ],
                            }
                        ],
                        "summary": title,
                        "themeColor": "778eb1",
                        "title": title,
                        "type": "MessageCard",
                    },
                }
            ],
        }

        if activity_image:
            message["attachments"][0]["content"]["sections"][0][
                "activityImage"
            ] = activity_image

        return message

    def set_title(self, message, title):
        """
        Set summary and title in an existing Teams message dictionary.
        """
        message["attachments"][0]["content"]["summary"] = title
        message["attachments"][0]["content"]["title"] = title
        return message

    def set_activity_title(self, message, activity_title):
        """
        Set activityTitle in an existing Teams message dictionary.
        """
        message["attachments"][0]["content"]["sections"][0][
            "activityTitle"
        ] = activity_title
        return message

    def set_activity_subtitle(self, message, activity_subtitle):
        """
        Set activitySubtitle in an existing Teams message dictionary.
        """
        message["attachments"][0]["content"]["sections"][0][
            "activitySubtitle"
        ] = activity_subtitle
        return message

    def set_activity_image(self, message, activity_image=""):
        """
        Set activityImage in an existing Teams message dictionary. If no image
        link is given or any other value that is considered False is given, the
        image will be removed.
        """
        if activity_image:
            message["attachments"][0]["content"]["sections"][0][
                "activityImage"
            ] = activity_image
        else:
            try:
                del message["attachments"][0]["content"]["sections"][0][
                    "activityImage"
                ]
            except KeyError:
                pass
        return message

    def add_fact(self, message, name, value):
        """
        Adds a facts dictionary to a Teams message dictionary.
        """
        message["attachments"][0]["content"]["sections"][0]["facts"] += [
            {"name": name, "value": value}
        ]
        return message

    def munki_message(self, message, munki_summary, verbosity):
        """
        Compiles the important results of MunkiImporter into a teams message.
        """
        data = munki_summary.get("data")
        name = data.get("name")
        version = data.get("version")
        catalogs = data.get("catalogs")
        pkginfo_path = data.get("pkginfo_path")
        pkg_repo_path = data.get("pkg_repo_path")
        icon_repo_path = data.get("icon_repo_path")
        self.output(f"          MunkiImporter name: {name}")
        self.output(f"       MunkiImporter version: {version}")
        self.output(f"      MunkiImporter catalogs: {catalogs}")
        self.output(f"  MunkiImporter pkginfo_path: {pkginfo_path}")
        self.output(f" MunkiImporter pkg_repo_path: {pkg_repo_path}")
        self.output(f"MunkiImporter icon_repo_path: {icon_repo_path}")
        message = self.add_fact(
            message,
            name,
            f"imported ver. {version} -> {catalogs}"
        )
        return (message)

    def staging_message(self, message, autostaging_summary, verbosity):
        """
        Compiles the important results of MunkiAutoStaging into a teams message.
        """
        data = autostaging_summary.get("data")
        name = data.get("name")
        versions = data.get("versions")
        munki_staging_catalog = data.get("staging_catalog")
        munki_production_catalog = data.get("production_catalog")
        self.output(f"                    AutoStaging name: {name}")
        self.output(f"                AutoStaging versions: {versions}")
        self.output(
            f"   AutoStaging munki_staging_catalog: {munki_staging_catalog}"
        )
        self.output(
            f"AutoStaging munki_production_catalog: {munki_production_catalog}"
        )
        message = self.add_fact(
            message,
            name,
            f"staged ver. {versions} {munki_staging_catalog} -> "
            f"{munki_production_catalog}"
        )
        return (message)

    def main(self):
        """
        Gets environment variables of MunkiImporter and MunkiAutoStaging and
        hands them to specialised methods for message creation.
        The message will be sent through a webhook to Teams if any relevant
        changes occured in the munki repository.
        """
        # Get all parameters
        teams_webhook_url = self.env.get("teams_webhook_url") or ""
        teams_username = self.env.get("teams_username") or "AutoPkg"
        teams_icon_url = (
            self.env.get("teams_icon_url")
            or "https://munkibuilds.org/logo.jpg"
        )

        munki_repo_changed = self.env.get("munki_repo_changed") or False
        munki_summary = self.env.get("munki_importer_summary_result") or ""
        autostaging_summary = \
            self.env.get("munki_autostaging_summary_result") or ""

        msg_file_path = self.env.get("msg_file_path") or ""
        msg_file_clear_at_start = \
            self.env.get("msg_file_clear_at_start") or False
        msg_file_clear_after_send = \
            self.env.get("msg_file_clear_after_send") or True
        msg_file_clear_at_finish = \
            self.env.get("msg_file_clear_at_finish") or False

        # Prepare / load message
        message = ""
        if msg_file_path and not msg_file_clear_at_start:
            with open(msg_file_path, 'r') as msg_file:
                try:
                    message = json.load(msg_file)
                except (IOError, OSError, JSONDecodeError):
                    self.output(
                        f"File {msg_file_path} could not be read or is not "
                        f"json formatted. Creating new message."
                    )

        if not message:
            message = self.new_message(
                title=teams_username,
                activity_image=teams_icon_url
            )
            self.set_activity_title(
                message,
                "start: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

        # Process repo changes
        if munki_repo_changed:
            if munki_summary:
                (message, munki_name) = self.munki_message(
                    message, munki_summary, verbosity
                )

            if autostaging_summary:
                (message, staging_name) = self.staging_message(
                    message, autostaging_summary, verbosity
                )

        if msg_file_path and not msg_file_clear_at_finish:
            with open(msg_file_path, 'w') as msg_file:
                try:
                    json.dump(message, msg_file)
                except (IOError, OSError) as file_error:
                    self.output(f"Failed witing file {msg_file_path}.")
                    raise file_error

        if teams_webhook_url:
            try:
                self.send_teams_message(teams_webhook_url, message)
                if msg_file_clear_after_send:
                    try:
                        os.remove(msg_file)
                    except (FileNotFoundError()):
                        pass
            except (ProcessorError) as teams_error:
                if msg_file_clear_at_finish:
                    try:
                        os.remove(msg_file)
                    except (FileNotFoundError()):
                        pass
                    raise teams_error
        
        if msg_file_clear_at_finish:
            try:
                os.remove(msg_file)
            except (FileNotFoundError()):
                pass

if __name__ == "__main__":
    PROCESSOR = MunkiRepoTeamsSummarizer()
    PROCESSOR.execute_shell()

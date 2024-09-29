import os
import os.path as osp
import zipfile
import csv
from django.db import transaction
from glob import glob
from pydub import AudioSegment
from cvat.apps.dataset_manager.bindings import InstanceLabelData
from cvat.apps.engine.serializers import LabeledDataSerializer
import cvat.apps.dataset_manager as dm
from cvat.apps.dataset_manager.task import PatchAction
from .registry import importer
from cvat.apps.engine.models import Job, Task, Data
from cvat.apps.engine.task import _create_thread
from cvat.apps.dataset_manager.bindings import ProjectData


def calculate_duration(row):
    start_time = float(row["start"])  # Assuming start and end times are in seconds
    end_time = float(row["end"])
    return end_time - start_time


def split_rows_by_time(all_rows, time_threshold=600):
    result = []

    total_duration = 0

    for row in all_rows:
        start_time = float(row["start"])
        end_time = float(row["end"])
        duration = end_time - start_time

        total_duration += duration

        if total_duration > time_threshold:
            # split logic here
            total_duration_till_previous_row = total_duration - duration
            remaining_time = time_threshold - total_duration_till_previous_row

            first_part = row.copy()
            first_part["end"] = str(float(first_part["start"]) + remaining_time)

            second_part = row.copy()
            second_part["start"] = first_part["end"]

            result.append(first_part)
            result.append(second_part)

            second_part_duration = float(second_part["end"]) - float(
                second_part["start"]
            )

            total_duration = second_part_duration

        else:
            result.append(row)

    return result


def load_anno(file_object, annotations):
    if isinstance(file_object, str):
        with open(file_object, "r", encoding="utf-8") as f:
            content = f.read()

    lines = content.splitlines()
    headers = lines[0].split("\t")

    label_data = InstanceLabelData(annotations.db_instance)

    task_id = annotations.db_instance.id
    task = Task.objects.get(id=task_id)
    jobs = Job.objects.filter(segment__task=task)

    for line in lines[1:]:
        fields = line.split("\t")
        record = dict(zip(headers, fields))

        if "job_id" in record:
            job_id = record.get("job_id")
        else:
            job_index_id = int(record.get("job index"))
            job_id = jobs[job_index_id].id

        start = float(record.get("start", 0))
        end = float(record.get("end", 0))

        label_name = record.get("label")
        label_id = label_data._get_label_id(label_name)

        attributes = []

        for i in range(1, len(headers)):
            attribute_name_key = f"attribute_{i}_name"
            attribute_value_key = f"attribute_{i}_value"

            if attribute_name_key in record and attribute_value_key in record:
                attribute_name = record.get(attribute_name_key)
                attribute_value = record.get(attribute_value_key)

                if attribute_name and attribute_value:

                    spec_id = label_data._get_attribute_id(label_id, attribute_name)

                    attributes.append(
                        {
                            "spec_id": spec_id,
                            "value": attribute_value,
                        }
                    )

        language_id_to_locale_mapping = {
            0: "en-US",
            1: "es-ES",
            2: "fr-FR",
            3: "zh-CN",
            4: "hi-IN",
            5: "ar-EG",
            6: "pt-BR",
            7: "ja-JP",
            8: "de-DE",
            9: "ru-RU",
        }

        # defaults to -1 if language field not in tsv, locale will be an empty string
        language_id = (
            int(float(record.get("language", -1))) if record.get("language") else -1
        )

        shapes_data = [
            {
                "type": "rectangle",
                "label": record.get("label", ""),
                "points": [start, start, end, end],
                "frame": 0,
                "occluded": False,
                "z_order": 0,
                "group": None,
                "source": "manual",
                "transcript": record.get("text", ""),
                "gender": record.get("gender", ""),
                "age": record.get("age", ""),
                "locale": language_id_to_locale_mapping.get(language_id, ""),
                "accent": record.get("accent", ""),
                "emotion": record.get("emotion", ""),
                "rotation": 0.0,
                "label_id": label_id,
                "attributes": attributes,
            }
        ]

        data = {"shapes": shapes_data}

        serializer = LabeledDataSerializer(data=data)
        pk = int(job_id)
        action = PatchAction.CREATE

        if serializer.is_valid(raise_exception=True):
            data = dm.task.patch_job_data(pk, serializer.data, action)


@importer(name="LibriVox", ext="TSV, ZIP", version=" ")
def _import(src_file, temp_dir, instance_data, load_data_callback=None, **kwargs):
    is_zip = zipfile.is_zipfile(src_file)
    src_file.seek(0)
    file_name = os.path.basename(src_file.name)
    name_without_extension = os.path.splitext(file_name)[0]

    if is_zip:
        zipfile.ZipFile(src_file).extractall(temp_dir)

        if isinstance(instance_data, ProjectData):
            project = instance_data.db_project
            new_task = Task.objects.create(
                project=project,
                name=name_without_extension,
                segment_size=0,
            )
            new_task.save()

            with transaction.atomic():
                locked_instance = Task.objects.select_for_update().get(pk=new_task.id)
                task_data = locked_instance.data
                if not task_data:
                    task_data = Data.objects.create()
                    task_data.make_dirs()
                    locked_instance.data = task_data
                    locked_instance.save()

            clips_folder = os.path.join(temp_dir, "clips")
            tsv_file_path = os.path.join(temp_dir, "data.tsv")

            with open(tsv_file_path, "r", newline="", encoding="utf-8") as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter="\t")
                tsv_rows = list(reader)

                num_tsv_rows = len(tsv_rows)
                num_clips = len(os.listdir(clips_folder))

                if num_tsv_rows != num_clips:
                    raise ValueError(
                        f"Import failed: {num_tsv_rows} rows in TSV but {num_clips} audio clips in the clips folder. The numbers must match."
                    )

            # Combined audio that will be the final output
            combined_audio = AudioSegment.empty()

            # Read TSV file to get the ordered list of audio files
            with open(tsv_file_path, "r", newline="", encoding="utf-8") as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter="\t")

                for row in reader:
                    audio_file_name = row[
                        "file"
                    ]  # Assuming 'file' column contains audio file names
                    file_path = os.path.join(clips_folder, audio_file_name)

                    if os.path.isfile(file_path):
                        audio_segment = AudioSegment.from_file(file_path)
                        combined_audio += (
                            audio_segment  # Append the audio in the order from TSV
                        )

            # Create raw folder to store combined audio
            raw_folder_path = os.path.join(task_data.get_data_dirname(), "raw")
            os.makedirs(raw_folder_path, exist_ok=True)

            combined_audio_path = os.path.join(raw_folder_path, "combined_audio.wav")
            combined_audio.export(combined_audio_path, format="wav")

            data = {
                "chunk_size": None,
                "image_quality": 70,
                "start_frame": 0,
                "stop_frame": None,
                "frame_filter": "",
                "client_files": ["combined_audio.wav"],
                "server_files": [],
                "remote_files": [],
                "use_zip_chunks": False,
                "server_files_exclude": [],
                "use_cache": False,
                "copy_data": False,
                "storage_method": "file_system",
                "storage": "local",
                "sorting_method": "lexicographical",
                "filename_pattern": None,
            }

            _create_thread(
                locked_instance, data, is_task_import=True, temp_dir=temp_dir
            )

            with open(tsv_file_path, "r", newline="", encoding="utf-8") as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter="\t")
                all_rows = list(reader)

                new_rows = split_rows_by_time(all_rows)

            jobs = Job.objects.filter(segment__task=locked_instance).order_by("id")

            label_data = InstanceLabelData(instance_data.db_project)

            record_index = 0
            for job in jobs:
                start_time = 0

                while record_index < len(new_rows):
                    record = new_rows[record_index]

                    record_duration = calculate_duration(record)

                    end_time = start_time + record_duration

                    label_name = record.get("label")
                    label_id = label_data._get_label_id(label_name)

                    attributes = []

                    # Process dynamic attribute_i_name and attribute_i_value fields
                    attribute_index = 1  # Start with the first attribute
                    while True:
                        attribute_name_key = f"attribute_{attribute_index}_name"
                        attribute_value_key = f"attribute_{attribute_index}_value"

                        # Check if the keys exist in the record
                        if (
                            attribute_name_key in record
                            and attribute_value_key in record
                        ):
                            attribute_name = record.get(attribute_name_key)
                            attribute_value = record.get(attribute_value_key)

                            if attribute_name and attribute_value:
                                spec_id = label_data._get_attribute_id(
                                    label_id, attribute_name
                                )
                                attributes.append(
                                    {
                                        "spec_id": spec_id,
                                        "value": attribute_value,
                                    }
                                )

                            attribute_index += 1  # Move to the next attribute index
                        else:
                            break  # Exit the loop when no more attributes are found

                    language_id_to_locale_mapping = {
                        0: "en-US",
                        1: "es-ES",
                        2: "fr-FR",
                        3: "zh-CN",
                        4: "hi-IN",
                        5: "ar-EG",
                        6: "pt-BR",
                        7: "ja-JP",
                        8: "de-DE",
                        9: "ru-RU",
                    }

                    # defaults to -1 if language field not in tsv, locale will be an empty string
                    language_id = (
                        int(float(record.get("language", -1)))
                        if record.get("language")
                        else -1
                    )

                    shapes_data = [
                        {
                            "type": "rectangle",
                            "label": record.get("label", ""),
                            "points": [start_time, start_time, end_time, end_time],
                            "frame": 0,
                            "occluded": False,
                            "z_order": 0,
                            "group": None,
                            "source": "manual",
                            "transcript": record.get("text", ""),
                            "gender": record.get("gender", ""),
                            "age": record.get("age", ""),
                            "locale": language_id_to_locale_mapping.get(
                                language_id, ""
                            ),
                            "accent": record.get("accent", ""),
                            "emotion": record.get("emotion", ""),
                            "rotation": 0.0,
                            "label_id": label_id,
                            "attributes": attributes,
                        }
                    ]

                    data = {"shapes": shapes_data}
                    start_time = end_time

                    serializer = LabeledDataSerializer(data=data)
                    pk = int(job.id)
                    action = PatchAction.CREATE

                    if serializer.is_valid(raise_exception=True):
                        data = dm.task.patch_job_data(pk, serializer.data, action)

                    record_index += 1
                    total_duration = round(end_time, 2)
                    if 599.9 <= total_duration <= 600:
                        break

        else:
            anno_paths = glob(osp.join(temp_dir, "**", "*.tsv"), recursive=True)
            for p in anno_paths:
                load_anno(p, instance_data)

import os.path as osp
import zipfile
from glob import glob
from cvat.apps.dataset_manager.bindings import InstanceLabelData
from cvat.apps.engine.serializers import LabeledDataSerializer
import cvat.apps.dataset_manager as dm
from cvat.apps.dataset_manager.task import PatchAction
from .registry import importer
from cvat.apps.engine.models import Task, Job


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

        language_id_to_locale_mapping = {0: "en"}
        language_id = int(record.get("language", 0))

        spec_id = label_data._get_attribute_id(label_id, record.get("attribute_1_name"))

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
                "transcript": record.get("sentence", ""),
                "gender": record.get("gender", ""),
                "age": record.get("age", ""),
                "locale": language_id_to_locale_mapping.get(language_id, ""),
                "accent": record.get("accents", ""),
                "emotion": record.get("emotion", ""),
                "rotation": 0.0,
                "label_id": label_id,
                "attributes": [
                    {
                        "spec_id": spec_id,
                        "value": record.get("attribute_1_value", ""),
                    }
                ],
            }
        ]

        data = {"shapes": shapes_data}

        serializer = LabeledDataSerializer(data=data)
        pk = int(job_id)
        action = PatchAction.CREATE

        if serializer.is_valid(raise_exception=True):
            data = dm.task.patch_job_data(pk, serializer.data, action)


@importer(name="Common Voice", ext="TSV, ZIP", version=" ")
def _import(src_file, temp_dir, instance_data, load_data_callback=None, **kwargs):
    is_zip = zipfile.is_zipfile(src_file)
    src_file.seek(0)
    if is_zip:
        zipfile.ZipFile(src_file).extractall(temp_dir)

        anno_paths = glob(osp.join(temp_dir, "**", "*.tsv"), recursive=True)
        for p in anno_paths:
            load_anno(p, instance_data)

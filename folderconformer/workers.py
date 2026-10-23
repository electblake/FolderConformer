from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from itertools import batched
from threading import Lock, local


DEFAULT_WORKER_THREADS = {"landscape": 1, "landscape_images": 1, "music_videos": 1, "checks": 1}
RULE_IDENTIFIERS = {
    "landscape": "H2", "extension": "N4", "rename_images": "F8", "rename_videos": "N2",
    "photo_extensions": "J1", "video_extensions": "S6", "remove_empty_dirs": "K9",
    "landscape_images": "B7", "data_extensions": "R3", "music_videos": "M5",
    "flatten_videos": "V1", "flatten_images": "I1", "non_video_to_root": "V2",
    "non_image_to_root": "I2", "create_empty_file": "E1",
}
_output_lock = Lock()


def report(message, *, flush=True):
    with _output_lock:
        print(message, flush=flush)


@contextmanager
def worker_results(function, items, threads):
    # Bound in-flight work and consume results in input order. Leaving the context
    # joins every worker before another rule can mutate the same files.
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        def results():
            for batch in batched(items, threads):
                futures[:] = [executor.submit(function, item) for item in batch]
                for item, future in zip(batch, futures):
                    yield item, future.result()
        yield results()
        for future in futures:
            future.result()


class MusicAnalysis:
    def __init__(self, audio_classes, ffprobe, control=None):
        self.audio_classes = tuple(tuple(entry) for entry in audio_classes)
        self.ffprobe = ffprobe
        self.control = control
        self.state = local()

    def __call__(self, path):
        if not hasattr(self.state, "detector"):
            from folderconformer.music import MusicDetector
            self.state.detector = MusicDetector(self.audio_classes)
        return self.state.detector.classify_video(path, self.ffprobe, self.control)

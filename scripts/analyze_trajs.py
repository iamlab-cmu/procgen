import argparse
import pickle
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_arguments(input_args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        required=True,
        help="Specifies a directory of Procgen episode trajectories.",
    )
    args = parser.parse_args(input_args)
    return args


def analyze_trajs(input_args):
    args = parse_arguments(input_args)

    assert args.input_dir.exists(), \
        f"Expected input_dir \"{args.input_dir}\" to exist, but it does not."
    traj_paths_unsorted = list(args.input_dir.glob('*.pickle'))

    # Sort trajectories by index in the filename
    first_traj_filekey = "000000000.pickle"
    first_traj_path_as_list = list(args.input_dir.glob(f'*{first_traj_filekey}'))
    assert len(first_traj_path_as_list) == 1
    first_traj_path = first_traj_path_as_list[0]
    traj_prefix = first_traj_path.name.split(first_traj_filekey)[0]
    if traj_prefix:
        for t in traj_paths_unsorted:
            assert traj_prefix in t.stem, \
                "Expected all trajectory paths to have the same prefix, but they do not."
        traj_indices_as_str = [t.stem.split(traj_prefix)[1] for t in traj_paths_unsorted]
    else:
        # This will throw an error if the filename isn't an integer, so no assert is needed
        traj_indices_as_str = [t.stem for t in traj_paths_unsorted]
    traj_indices = [int(t) for t in traj_indices_as_str]
    idx_traj_sort = np.argsort(traj_indices)
    traj_paths = np.array(traj_paths_unsorted)[idx_traj_sort].tolist()
    num_trajs = len(traj_paths)

    trajectories = []
    for traj_path in traj_paths:
        with open(traj_path, "rb") as f:
            trajectory = pickle.load(f)
        trajectories.append(trajectory)

    for idx_traj, (traj_path, trajectory) in enumerate(zip(traj_paths, trajectories)):

        traj_reward = np.sum(trajectory['reward'])
        last_human_frame = trajectory['info'][-1]['rgb']
        episode_len = len(trajectory['reward'])
        assert episode_len == len(trajectory['info'])
        level_seed_array = [i['level_seed'] for i in trajectory['info']]
        level_seed_unique = np.unique(level_seed_array)
        assert len(level_seed_unique) == 1
        level_seed = level_seed_unique[0]

        if (idx_traj + 1) < num_trajs:
            first_info_next_traj = trajectories[idx_traj+1]['info'][0]
            level_complete = first_info_next_traj['prev_level_complete']
            level_progress_at_end = first_info_next_traj['prev_level_progress']
            level_progress_max = first_info_next_traj['prev_level_progress_max']
        else:
            level_complete = "determine by reward"
            level_progress_at_end = trajectory['info'][-1]['level_progress']
            level_progress_max = trajectory['info'][-1]['level_progress_max']

        print(traj_path)
        print(f" - Level seed: {level_seed}")
        print(f" - Episode length: {episode_len}")
        print(f" - Episode reward: {traj_reward}")
        print(f" - Level complete: {level_complete}")
        print(f" - Level progress at episode end: {level_progress_at_end}")
        print(f" - Max achieved level progress: {level_progress_max}")
        print()

        plt.imshow(last_human_frame)
        plt.show()

if __name__ == "__main__":
    analyze_trajs(sys.argv[1:])

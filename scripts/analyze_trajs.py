import argparse
import pickle
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from ruamel.yaml import YAML


ENV_REWARD_SOLVED_THRESHOLD = {
    "climber": 10.0,
    "coinrun": 10.0,
    "heist": 10.0,
    "leaper": 10.0,
}


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


def get_traj_paths_from_dir(input_dir):
    traj_paths_unsorted = list(input_dir.glob('*.pickle'))
    if len(traj_paths_unsorted) == 0:
        return []

    # Sort trajectories by index in the filename
    first_traj_filekey = "000000000.pickle"
    first_traj_path_as_list = list(input_dir.glob(f'*{first_traj_filekey}'))
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
    return traj_paths


def analyze_trajs(input_args):
    args = parse_arguments(input_args)

    assert args.input_dir.exists(), \
        f"Expected input_dir \"{args.input_dir}\" to exist, but it does not."
    traj_paths = get_traj_paths_from_dir(args.input_dir)
    if len(traj_paths) > 0:
        # Assume there are no subdirectories
        traj_sequences = [traj_paths]
    else:
        # Assume there are subdirectories
        dir_dirs = [dir for dir in args.input_dir.iterdir() if dir.is_dir()]

        traj_sequences_unsorted = []
        candidate_dirs_time = []
        for dir in dir_dirs:
            try:
                dir_time = datetime.strptime(dir.name, "%Y-%m-%d-%H-%M-%S")

                dir_traj_paths = get_traj_paths_from_dir(dir)
                if len(dir_traj_paths) > 0:
                    traj_sequences_unsorted.append(dir_traj_paths)
                    candidate_dirs_time.append(dir_time)
                else:
                    # Just warn for now
                    print(f"Directory \"{dir}\" has a valid timestamp name but contains no data.")
            except:
                pass

        idx_dir_sort = np.argsort(candidate_dirs_time)
        traj_sequences = [traj_sequences_unsorted[x] for x in idx_dir_sort]

    # Loop through trajectory sequences
    for traj_paths in traj_sequences:

        num_trajs = len(traj_paths)

        trajectories = []
        for traj_path in traj_paths:
            with open(traj_path, "rb") as f:
                trajectory = pickle.load(f)
            trajectories.append(trajectory)

        # Open info file, if it exists
        info_path = traj_path.parent / "info.yaml"
        if info_path.exists():
            yaml = YAML(typ="safe")
            with open(info_path, "r") as f:
                info_dict = yaml.load(f)
        else:
            info_dict = {}

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
                if "env_name" in info_dict:
                    env_name = info_dict["env_name"].lower()
                    if env_name in ENV_REWARD_SOLVED_THRESHOLD:
                        level_complete = 1 if traj_reward >= ENV_REWARD_SOLVED_THRESHOLD[env_name] else 0
                    else:
                        level_complete = "determine by reward (env reward threshold not implemented)"
                else:
                    level_complete = "determine by reward"
                level_progress_at_end = trajectory['info'][-1]['level_progress']
                level_progress_max = trajectory['info'][-1]['level_progress_max']

            print(traj_path)
            if "env_name" in info_dict:
                print(f" - Env name: {info_dict['env_name']}")
            print(f" - Level seed: {level_seed}")
            if "level_options" in info_dict:
                print(f" - Level options: {info_dict['level_options']}")
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

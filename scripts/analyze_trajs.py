import argparse
import pickle
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ruamel.yaml import YAML


ENV_REWARD_SOLVED_THRESHOLD = {
    "climber": 10.0,
    "coinrun": 10.0,
    "heist": 10.0,
    "leaper": 10.0,
    "chaser": 10.0,
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
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="If provdided, specifies a directory where additional output results will be saved.",
    )
    parser.add_argument(
        "-f",
        "--force-output",
        action="store_true",
        default=False,
        help="If provided, specifies that the output results will be overwritten.",
    )
    parser.add_argument(
        "-p",
        "--use-raw-progress",
        action="store_true",
        default=False,
        help="If specified, do not round up level progress metrics upon a level being complete.",
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

    # Parse arguments
    args = parse_arguments(input_args)

    if args.output_dir is not None:
        save_results = True

        if args.output_dir.exists():
            assert args.force_output, \
                f"Output directory \"{args.output_dir}\" already exists."
    else:
        save_results = False

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

    # Prepare spreadsheet data
    if save_results:
        all_traj_parents = []
        all_traj_filenames = []
        all_traj_names = []
        all_traj_seeds = []
        all_traj_options1 = []
        all_traj_options2 = []
        all_traj_lengths = []
        all_traj_rewards = []
        all_traj_completes = []
        all_traj_progress = []
        all_traj_max_progress = []

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

            if not args.use_raw_progress and level_complete == 1:
                level_progress_at_end = 100
                level_progress_max = 100

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

            if save_results:
                all_traj_parents.append(traj_path.parent)
                all_traj_filenames.append(traj_path.name)
                if "env_name" in info_dict:
                    all_traj_names.append(info_dict["env_name"])
                else:
                    # by default, "coinrun" is chosen by procgen if env-name isn't specified
                    # so it isn't possible for info.yaml to exist without the field env_name
                    # therefore, we don't need to check for that case
                    all_traj_names.append("unknown")
                all_traj_seeds.append(level_seed)
                if "level_options" in info_dict:
                    level_options_len = len(info_dict["level_options"])
                    if level_options_len > 0:
                        all_traj_options1.append(info_dict["level_options"][0])
                    elif info_dict:
                        all_traj_options1.append(-1)
                    else:
                        all_traj_options1.append("unknown")
                    if level_options_len > 1:
                        all_traj_options2.append(info_dict["level_options"][1])
                    elif info_dict:
                        all_traj_options2.append(-1)
                    else:
                        all_traj_options2.append("unknown")
                elif info_dict:
                    # info.yaml exists, but level_options was not specified -- defaults are used
                    all_traj_options1.append(-1)
                    all_traj_options2.append(-1)
                else:
                    # info.yaml does not exist -- can't determine
                    all_traj_options1.append("unknown")
                    all_traj_options2.append("unknown")
                all_traj_lengths.append(episode_len)
                all_traj_rewards.append(traj_reward)
                all_traj_completes.append(level_complete)
                all_traj_progress.append(level_progress_at_end)
                all_traj_max_progress.append(level_progress_max)

    if save_results:

        all_traj_trials = list(range(1, len(all_traj_parents) + 1))
        df_data = [
            all_traj_trials,
            all_traj_parents,
            all_traj_filenames,
        ]
        df_index_names = [
            "Trial",
            "Path",
            "Filename",
        ]
        if all_traj_names:
            df_data.append(all_traj_names)
            df_index_names.append("Env name")
        df_data.append(all_traj_seeds)
        df_index_names.append("Level seed")
        if all_traj_options1:
            df_data.append(all_traj_options1)
            df_index_names.append("Level option 1")
        if all_traj_options2:
            df_data.append(all_traj_options2)
            df_index_names.append("Level option 2")
        df_data.append(all_traj_lengths)
        df_index_names.append("Episode length")
        df_data.append(all_traj_rewards)
        df_index_names.append("Episode reward")
        df_data.append(all_traj_completes)
        df_index_names.append("Level complete")
        df_data.append(all_traj_progress)
        df_index_names.append("Level progress")
        df_data.append(all_traj_max_progress)
        df_index_names.append("Max level progress")

        df = pd.DataFrame(
            df_data,
            index=df_index_names,
        ).T

        args.output_dir.mkdir(parents=True, exist_ok=True)
        sheet_path = args.output_dir / "results.xlsx"

        # adapted from https://stackoverflow.com/a/61617835
        writer = pd.ExcelWriter(sheet_path, engine="xlsxwriter")
        df.to_excel(writer, sheet_name='Results', index=False, na_rep='NaN')
        for column in df:
            column_length = max(df[column].astype(str).map(len).max(), len(column))
            col_idx = df.columns.get_loc(column)
            writer.sheets['Results'].set_column(col_idx, col_idx, column_length)
        writer.save()

if __name__ == "__main__":
    analyze_trajs(sys.argv[1:])

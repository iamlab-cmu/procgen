#!/usr/bin/env python
import argparse
from datetime import datetime
from pathlib import Path

from procgen import ProcgenGym3Env
from .env import ENV_NAMES
from gym3 import Interactive, TrajectoryRecorderWrapper, VideoRecorderWrapper, unwrap


class ProcgenInteractive(Interactive):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_state = None

    def _update(self, dt, keys_clicked, keys_pressed):
        if "LEFT_SHIFT" in keys_pressed and "F1" in keys_clicked:
            print("save state")
            self._saved_state = unwrap(self._env).get_state()
        elif "F1" in keys_clicked:
            print("load state")
            if self._saved_state is not None:
                unwrap(self._env).set_state(self._saved_state)
        super()._update(dt, keys_clicked, keys_pressed)


def make_interactive(vision, record_dir, traj_dir, traj_prefix, traj_log_method, **kwargs):
    info_key = None
    ob_key = None
    if vision == "human":
        info_key = "rgb"
        kwargs["render_mode"] = "rgb_array"
    else:
        ob_key = "rgb"

    env = ProcgenGym3Env(num=1, **kwargs)
    if record_dir is not None:
        env = VideoRecorderWrapper(
            env=env, directory=record_dir, ob_key=ob_key, info_key=info_key
        )
    if traj_dir is not None:
        if traj_log_method == "direct":
            traj_path = Path(traj_dir)
        elif traj_log_method == "append":
            now = datetime.now()
            timestr = now.strftime("%Y-%m-%d-%H-%M-%S")
            traj_path = Path(traj_dir) / timestr
        else:
            raise NotImplementedError
        assert not traj_path.exists(), \
            f"Expected traj_path \"{traj_dir}\" to not exist, but it already exists."
        env = TrajectoryRecorderWrapper(
            env=env,
            directory=traj_path,
            filename_prefix=traj_prefix,
        )
    h, w, _ = env.ob_space["rgb"].shape
    return ProcgenInteractive(
        env,
        ob_key=ob_key,
        info_key=info_key,
        width=w * 12,
        height=h * 12,
    )


def main():
    default_str = "(default: %(default)s)"
    parser = argparse.ArgumentParser(
        description="Interactive version of Procgen allowing you to play the games"
    )
    parser.add_argument(
        "--vision",
        default="human",
        choices=["agent", "human"],
        help="level of fidelity of observation " + default_str,
    )
    parser.add_argument("--record-dir", help="directory to record movies to")
    parser.add_argument(
        "--distribution-mode",
        default="hard",
        help="which distribution mode to use for the level generation " + default_str,
    )
    parser.add_argument(
        "--env-name",
        default="coinrun",
        help="name of game to create " + default_str,
        choices=ENV_NAMES + ["coinrun_old"],
    )
    parser.add_argument(
        "--level-seed", type=int, help="select an individual level to use"
    )
    parser.add_argument(
        "--level-options",
        nargs="+",
        type=int,
        help="specify options for the particular level"
    )
    parser.add_argument(
        "--traj-dir",
        help="Specifies the output directory for episode trajectory logging.",
    )
    parser.add_argument(
        "--traj-prefix",
        default="",
        help="Specifies the prefix for logged episode trajectories.",
    )
    parser.add_argument(
        "--traj-log-method",
        default="append",
        choices=["append", "direct"],
        help="Specifies how the trajectories should be logged.",
    )

    advanced_group = parser.add_argument_group("advanced optional switch arguments")
    advanced_group.add_argument(
        "--paint-vel-info",
        action="store_true",
        default=False,
        help="paint player velocity info in the top left corner",
    )
    advanced_group.add_argument(
        "--use-generated-assets",
        action="store_true",
        default=False,
        help="use randomly generated assets in place of human designed assets",
    )
    advanced_group.add_argument(
        "--uncenter-agent",
        action="store_true",
        default=False,
        help="display the full level for games that center the observation to the agent",
    )
    advanced_group.add_argument(
        "--disable-backgrounds",
        action="store_true",
        default=False,
        help="disable human designed backgrounds",
    )
    advanced_group.add_argument(
        "--restrict-themes",
        action="store_true",
        default=False,
        help="restricts games that use multiple themes to use a single theme",
    )
    advanced_group.add_argument(
        "--use-monochrome-assets",
        action="store_true",
        default=False,
        help="use monochromatic rectangles instead of human designed assets",
    )

    args = parser.parse_args()

    kwargs = {
        "paint_vel_info": args.paint_vel_info,
        "use_generated_assets": args.use_generated_assets,
        "center_agent": not args.uncenter_agent,
        "use_backgrounds": not args.disable_backgrounds,
        "restrict_themes": args.restrict_themes,
        "use_monochrome_assets": args.use_monochrome_assets,
    }
    if args.env_name != "coinrun_old":
        kwargs["distribution_mode"] = args.distribution_mode
    if args.level_seed is not None:
        kwargs["start_level"] = args.level_seed
        kwargs["num_levels"] = 1
    if args.level_options is not None:
        kwargs["level_options"] = args.level_options
    ia = make_interactive(
        args.vision, record_dir=args.record_dir, traj_dir=args.traj_dir, traj_prefix=args.traj_prefix, traj_log_method=args.traj_log_method, env_name=args.env_name, **kwargs
    )
    ia.run()


if __name__ == "__main__":
    main()

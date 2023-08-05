#include "../basic-abstract-game.h"
#include "../assetgen.h"
#include <set>
#include <queue>
#include "../mazegen.h"
#include "../cpp-utils.h"

const std::string NAME = "heist";

const float COMPLETION_BONUS = 10.0f;

const int LOCKED_DOOR = 1;
const int KEY = 2;
const int EXIT = 9;
const int KEY_ON_RING = 11;

class HeistGame : public BasicAbstractGame {
  public:
    std::shared_ptr<MazeGen> maze_gen;
    int world_dim = 0;
    int num_keys = 0;
    std::vector<bool> has_keys;
    int keys_collected = 0;
    int num_doors_unlocked = 0;
    std::vector <float> keys_x;
    std::vector <float> keys_y;
    std::vector <float> doors_x;
    std::vector <float> doors_y;
    float exit_x = 0.0f;
    float exit_y = 0.0f;
    int current_stage = 0;
    int total_stages = 0;
    float last_stage_x = 0.0f;
    float last_stage_y = 0.0f;
    float next_stage_x = 0.0f;
    float next_stage_y = 0.0f;

    HeistGame()
        : BasicAbstractGame(NAME) {
        maze_gen = nullptr;
        has_useful_vel_info = false;

        main_width = 20;
        main_height = 20;

        out_of_bounds_object = WALL_OBJ;
        visibility = 8.0;
    }

    void load_background_images() override {
        main_bg_images_ptr = &topdown_backgrounds;
    }

    bool should_preserve_type_themes(int type) override {
        return type == KEY || type == LOCKED_DOOR;
    }

    void asset_for_type(int type, std::vector<std::string> &names) override {
        if (type == WALL_OBJ) {
            names.push_back("kenney/Ground/Dirt/dirtCenter.png");
        } else if (type == EXIT) {
            names.push_back("misc_assets/gemYellow.png");
        } else if (type == PLAYER) {
            names.push_back("misc_assets/spaceAstronauts_008.png");
        } else if (type == KEY) {
            names.push_back("misc_assets/keyBlue.png");
            names.push_back("misc_assets/keyGreen.png");
            names.push_back("misc_assets/keyRed.png");
            names.push_back("misc_assets/keyYellow.png");
        } else if (type == LOCKED_DOOR) {
            names.push_back("misc_assets/lock_blue.png");
            names.push_back("misc_assets/lock_green.png");
            names.push_back("misc_assets/lock_red.png");
            names.push_back("misc_assets/lock_yellow.png");
        }
    }

    bool use_block_asset(int type) override {
        return BasicAbstractGame::use_block_asset(type) || (type == WALL_OBJ) || (type == LOCKED_DOOR);
    }

    bool is_blocked_ents(const std::shared_ptr<Entity> &src, const std::shared_ptr<Entity> &target, bool is_horizontal) override {
        if (target->type == LOCKED_DOOR)
            return !has_keys[target->image_theme];

        return BasicAbstractGame::is_blocked_ents(src, target, is_horizontal);
    }

    bool should_draw_entity(const std::shared_ptr<Entity> &entity) override {
        if (entity->type == KEY_ON_RING)
            return has_keys[entity->image_theme];

        return BasicAbstractGame::should_draw_entity(entity);
    }

    void handle_agent_collision(const std::shared_ptr<Entity> &obj) override {
        BasicAbstractGame::handle_agent_collision(obj);

        if (obj->type == EXIT) {
            step_data.done = true;
            step_data.reward = COMPLETION_BONUS;
            step_data.level_complete = true;
        } else if (obj->type == KEY) {
            obj->will_erase = true;
            has_keys[obj->image_theme] = true;
            keys_collected++;
            update_stage();
        } else if (obj->type == LOCKED_DOOR) {
            int door_num = obj->image_theme;
            if (has_keys[door_num]) {
                obj->will_erase = true;
                num_doors_unlocked++;
                update_stage();
            }
        }
    }

    void choose_world_dim() override {
        int dist_diff = options.distribution_mode;

        if (dist_diff == EasyMode) {
            world_dim = 9;
        } else if (dist_diff == HardMode) {
            world_dim = 13;
        } else if (dist_diff == MemoryMode) {
            world_dim = 23;
        }

        maxspeed = .75;

        main_width = world_dim;
        main_height = world_dim;
    }

    void game_reset() override {
        BasicAbstractGame::game_reset();

        int min_maze_dim = 5;
        int max_diff = (world_dim - min_maze_dim) / 2;
        int difficulty = rand_gen.randn(max_diff + 1);
        keys_collected = 0;
        num_doors_unlocked = 0;

        options.center_agent = options.distribution_mode == MemoryMode;

        if (options.distribution_mode == MemoryMode) {
            num_keys = rand_gen.randn(4);
        } else {
            num_keys = difficulty + rand_gen.randn(2);
        }

        if (num_keys > 3)
            num_keys = 3;
        if (options.level_options_2 != -1) {
            num_keys = options.level_options_2;
        }

        has_keys.clear();

        for (int i = 0; i < num_keys; i++) {
            has_keys.push_back(false);
        }

        keys_x.clear();
        keys_y.clear();
        doors_x.clear();
        doors_y.clear();
        for (int i = 0; i < num_keys; i++) {
            keys_x.push_back(0.0f);
            keys_y.push_back(0.0f);
            doors_x.push_back(0.0f);
            doors_y.push_back(0.0f);
        }
        current_stage = 0;
        total_stages = 2*num_keys + 1;

        // int maze_dim = difficulty * 2 + min_maze_dim;
        int maze_dim = (options.level_options_1 == -1) ? (difficulty * 2 + min_maze_dim) : options.level_options_1;
        float maze_scale = main_height / (world_dim * 1.0);

        agent->rx = .375 * maze_scale;
        agent->ry = .375 * maze_scale;

        float r_ent = maze_scale / 2;

        maze_gen = std::make_shared<MazeGen>(&rand_gen, maze_dim);
        maze_gen->generate_maze_with_doors(num_keys);

        // move agent out of the way for maze generation
        agent->x = -1;
        agent->y = -1;

        int off_x = rand_gen.randn(world_dim - maze_dim + 1);
        int off_y = rand_gen.randn(world_dim - maze_dim + 1);

        for (int i = 0; i < grid_size; i++) {
            set_obj(i, WALL_OBJ);
        }

        for (int i = 0; i < maze_dim; i++) {
            for (int j = 0; j < maze_dim; j++) {
                int x = off_x + i;
                int y = off_y + j;

                int obj = maze_gen->grid.get(i + MAZE_OFFSET, j + MAZE_OFFSET);

                float obj_x = (x + .5) * maze_scale;
                float obj_y = (y + .5) * maze_scale;

                if (obj != WALL_OBJ) {
                    set_obj(x, y, SPACE);
                }

                if (obj >= KEY_OBJ) {
                    auto ent = spawn_entity(.375 * maze_scale, KEY, maze_scale * x, maze_scale * y, maze_scale, maze_scale);
                    ent->image_theme = obj - KEY_OBJ - 1;
                    match_aspect_ratio(ent);
                    keys_x[ent->image_theme] = obj_x;
                    keys_y[ent->image_theme] = obj_y;
                } else if (obj >= DOOR_OBJ) {
                    auto ent = add_entity(obj_x, obj_y, 0, 0, r_ent, LOCKED_DOOR);
                    ent->image_theme = obj - DOOR_OBJ - 1;
                    doors_x[ent->image_theme] = obj_x;
                    doors_y[ent->image_theme] = obj_y;
                } else if (obj == EXIT_OBJ) {
                    auto ent = spawn_entity(.375 * maze_scale, EXIT, maze_scale * x, maze_scale * y, maze_scale, maze_scale);
                    match_aspect_ratio(ent);
                    exit_x = obj_x;
                    exit_y = obj_y;
                } else if (obj == AGENT_OBJ) {
                    agent->x = obj_x;
                    agent->y = obj_y;
                }
            }
        }

        float ring_key_r = 0.03f;

        for (int i = 0; i < num_keys; i++) {
            auto ent = add_entity(1 - ring_key_r * (2 * i + 1.25), ring_key_r * .75, 0, 0, ring_key_r, KEY_ON_RING);
            ent->image_theme = i;
            ent->image_type = KEY;
            ent->rotation = PI / 2;
            ent->render_z = 1;
            ent->use_abs_coords = true;
            match_aspect_ratio(ent);
        }

        last_stage_x = agent->x;
        last_stage_y = agent->y;
        if (num_keys == 0) {
            next_stage_x = exit_x;
            next_stage_y = exit_y;
        } else {
            next_stage_x = keys_x[0];
            next_stage_y = keys_y[0];
        }
    }

    void game_step() override {
        BasicAbstractGame::game_step();

        agent->face_direction(action_vx, action_vy);
    }

    void serialize(WriteBuffer *b) override {
        BasicAbstractGame::serialize(b);
        b->write_int(num_keys);
        b->write_int(world_dim);
        b->write_vector_bool(has_keys);
        b->write_vector_float(keys_x);
        b->write_vector_float(keys_y);
        b->write_vector_float(doors_x);
        b->write_vector_float(doors_y);
        b->write_float(exit_x);
        b->write_float(exit_y);
        b->write_int(current_stage);
        b->write_int(total_stages);
        b->write_float(last_stage_x);
        b->write_float(last_stage_y);
        b->write_float(next_stage_x);
        b->write_float(next_stage_y);
    }

    void deserialize(ReadBuffer *b) override {
        BasicAbstractGame::deserialize(b);
        num_keys = b->read_int();
        world_dim = b->read_int();
        has_keys = b->read_vector_bool();
        keys_x = b->read_vector_float();
        keys_y = b->read_vector_float();
        doors_x = b->read_vector_float();
        doors_y = b->read_vector_float();
        exit_x = b->read_float();
        exit_y = b->read_float();
        current_stage = b->read_int();
        total_stages = b->read_int();
        last_stage_x = b->read_float();
        last_stage_y = b->read_float();
        next_stage_x = b->read_float();
        next_stage_y = b->read_float();
    }

    void observe() override {
        Game::observe();

        float dist_between_stages = pow(pow(next_stage_x - last_stage_x, 2.0f) + pow(next_stage_y - last_stage_y, 2.0f), 0.5f);
        float dist_to_next_stage = pow(pow(next_stage_x - agent->x, 2.0f) + pow(next_stage_y - agent->y, 2.0f), 0.5f);

        float slope = (dist_between_stages == 0.0f) ? 1000000.0f : -1.0f/dist_between_stages;
        int interp_progress = std::lround((slope*dist_to_next_stage + float(current_stage) + 1)/float(total_stages)*100.0f);

        level_progress = (interp_progress > level_progress) ? interp_progress : level_progress;
        level_progress_max = (level_progress > level_progress_max) ? level_progress : level_progress_max;
        *(int32_t *)(info_bufs[info_name_to_offset.at("level_progress")]) = level_progress;
        *(int32_t *)(info_bufs[info_name_to_offset.at("level_progress_max")]) = level_progress_max;
    }

    void set_action_xy(int move_action) override {
        // Reduce agent velocity when either level_options has been specified, keep original velocity otherwise
        float vel_factor = (options.level_options_1 == -1 && options.level_options_2 == -1) ? 1.0f : 0.5f;

        action_vx = (move_action / 3 - 1)*vel_factor;
        action_vy = (move_action % 3 - 1)*vel_factor;
        action_vrot = 0;
    }

    void update_stage() {
        current_stage++;

        last_stage_x = next_stage_x;
        last_stage_y = next_stage_y;

        if (num_doors_unlocked == num_keys) {
            // Next stage is the exit
            next_stage_x = exit_x;
            next_stage_y = exit_y;
        } else if (keys_collected == num_doors_unlocked) {
            // Next stage is a key
            next_stage_x = keys_x[keys_collected];
            next_stage_y = keys_y[keys_collected];
        } else {
            // Next stage is a door
            next_stage_x = doors_x[num_doors_unlocked];
            next_stage_y = doors_y[num_doors_unlocked];
        }
    }
};

REGISTER_GAME(NAME, HeistGame);

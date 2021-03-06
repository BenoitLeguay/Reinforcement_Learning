import numpy as np
import torch
import variable as v
import utils
from copy import deepcopy

#  https://arxiv.org/pdf/1810.09967.pdf


class DQNAgent:
    def __init__(self, agent_init):
        self.policy_type = agent_init["policy_type"]
        self.exploration_handler = utils.ExplorationRateDecay(*agent_init["exploration_rate"].values())
        self.temperature = agent_init["temperature"]
        self.num_action = agent_init["num_action"]
        self.dqn_handler = utils.DQNHandler(agent_init["neural_network_handler"], agent_init['optim'], agent_init['replay_buffer'])
        self.max_position = agent_init["max_position_init"]
        self.max_position_reward_bonus = agent_init["max_position_reward_bonus"]
        self.random_generator = np.random.RandomState(seed=agent_init['seed'])
        self.early_stop = utils.EarlyStop(*agent_init["early_stop"].values())
        self.next_state = None
        self.next_action = None

    @staticmethod
    def flatten_state(state):
        return np.ravel(state)

    def policy(self, state):

        state_tensor = self.dqn_handler.to_float_tensor(state)
        values = self.dqn_handler.eval_nn(state_tensor).detach()

        if self.policy_type == 'e-greedy':
            action = self.e_greedy(values)
        elif self.policy_type == 'softmax':
            action = self.softmax(values)
        else:
            raise ValueError(f"Agent does not handle {self.policy_type} policy")

        return action

    def softmax(self, values):
        values = values.data.numpy()

        values_temp = values / self.temperature
        exp_values_temp = np.exp(values_temp - np.max(values_temp, axis=0))
        softmax_values = exp_values_temp / np.sum(exp_values_temp)

        action = self.random_generator.choice(self.num_action, p=softmax_values)

        return action

    def e_greedy(self, values):

        if self.random_generator.rand() < self.exploration_handler():
            action = self.random_generator.randint(self.num_action)
        else:
            action = values.max(0)[1].item()

        return action

    def max_position_reward_function(self, new_position, reward):
        if new_position > self.max_position:
            self.max_position = new_position
            reward += self.max_position_reward_bonus

        return reward

    def episode_init(self, state):
        state = self.flatten_state(state)

        action = self.policy(state)
        self.next_action = action
        self.next_state = state

        return action

    def update(self, state, reward, done):
        state = self.flatten_state(state)

        reward = self.max_position_reward_function(state[0], reward)

        next_action = -1
        if not done:
            next_action = self.update_step(state, reward)
        if done:
            self.update_end(reward)

        return next_action

    def update_step(self, next_state, reward):
        current_action = self.next_action
        current_state = self.next_state

        skip_training = self.early_stop.skip_episode()
        self.dqn_handler.update_step(current_state, current_action, reward, next_state, 0, skip_training)

        next_action = self.policy(next_state)

        self.next_state = next_state
        self.next_action = next_action

        return next_action

    def update_end(self, reward):
        current_action = self.next_action
        current_state = self.next_state

        skip_training = self.early_stop.skip_episode()
        self.dqn_handler.update_step(current_state, current_action, reward, current_state, 1, skip_training)


class DDQNAgent(DQNAgent):
    def __init__(self, agent_init):
        super().__init__(agent_init)
        self.dqn_handler = utils.DDQNHandler(agent_init["neural_network_handler"], agent_init['optim'], agent_init['replay_buffer'])


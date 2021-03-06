import numpy as np
import gym
from gym import spaces
from estimations import Estimator


class NYCEnv(gym.Env):
    def __init__(self, delta_t=10):
        super(NYCEnv, self).__init__()
        self.NUM_TAXI_ZONES = 263
        self.SHIFT_START_TIME = 60 // delta_t * 8
        self.SHIFT_DURATION = 60 // delta_t * 8
        self.FUEL_UNIT_PRICE = .125
        self.TERMINATE_PENALTY = -10000
        self.delta_t = delta_t
        self.action_space = spaces.Discrete(self.NUM_TAXI_ZONES + 1)
        self.observation_space = spaces.Box(
            low=np.array([1, self.SHIFT_START_TIME]),
            high=np.array(
                [self.NUM_TAXI_ZONES, self.SHIFT_START_TIME + self.SHIFT_DURATION]),
            dtype=np.int32,
        )
        self.estimator = Estimator(delta_t=delta_t)

    def step(self, action):
        if action == 0:
            return self._wait()
        if action == self.current_taxi_zone:
            return self._hunt()
        if not self.estimator.is_adjacent(action, self.current_taxi_zone):
            return self._fly()
        return self._cruise_to_adjacent_taxi_zone(action)

    def reset(self):
        self.total_rewards = 0
        self.current_taxi_zone = np.random.randint(1, self.NUM_TAXI_ZONES + 1)
        self.current_time = self.SHIFT_START_TIME
        return np.array([self.current_taxi_zone, self.current_time])

    def render(self, mode='console'):
        if mode != 'console':
            return NotImplementedError('Mode other than console is not yet implemented.')
        print(
            f'Current taxi zone: {self.current_taxi_zone}, time: {self.current_time}, reward: {self.total_rewards:.2f}'
        )

    def _check_done(self):
        return self.current_time > self.SHIFT_START_TIME + self.SHIFT_DURATION

    def _wait(self):
        self.current_time += 1
        info = {}
        return np.array([self.current_taxi_zone, self.current_time]), 0, self._check_done(), info

    def _hunt(self):
        self.current_time += self.estimator.cruise_time(self.current_taxi_zone, self.current_time)
        info = {}
        if self._check_done():
            return np.array([self.current_taxi_zone, self.current_time]), 0, True, info
        # generate next request with probability
        prob = np.random.rand()
        prob_threshold = self.estimator.matching_prob(self.current_time, self.current_taxi_zone)
        if prob < prob_threshold:
            dst = self.estimator.generate_request(self.current_taxi_zone, self.current_time)
            self.current_time += self.estimator.trip_time(self.current_taxi_zone, dst, self.current_time)
            reward = self.estimator.trip_fare(self.current_taxi_zone, dst, self.current_time)
            reward -= self.FUEL_UNIT_PRICE * self.estimator.trip_distance(self.current_taxi_zone, dst)
            self.current_taxi_zone = dst
        else:
            self.current_time += 1
            reward = 0
        self.total_rewards += reward
        return np.array([self.current_taxi_zone, self.current_time]), reward, self._check_done(), info

    def _fly(self):
        reward = self.TERMINATE_PENALTY
        info = {}
        self.total_rewards += reward
        self.current_time += self.SHIFT_DURATION
        return np.array([self.current_taxi_zone, self.current_time]), reward, True, info

    def _cruise_to_adjacent_taxi_zone(self, action):
        reward = -self.FUEL_UNIT_PRICE * self.estimator.trip_distance(self.current_taxi_zone, action)
        info = {}
        self.current_taxi_zone = action
        self.current_time += self.estimator.trip_time(self.current_taxi_zone, action, self.current_time)
        return np.array([self.current_taxi_zone, self.current_time]), reward, self._check_done(), info

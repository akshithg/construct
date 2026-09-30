"""Correct-by-construction genetic synthesis of symbol mappings."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

EXACT_MSE = 1e-20
_MIN_POPULATION = 4
_MIN_PERMUTATION_LENGTH = 2
_INPUT_MUTATION_PROBABILITY = 0.35
_MUTATION_PROBABILITY = 0.8


@dataclass(frozen=True)
class Genome:
    """A causality-preserving mapping from AST slots to FMU names."""

    inputs: tuple[str, ...]
    parameters: tuple[str, ...]


@dataclass(frozen=True)
class SynthesisResult:
    """Best recovered mapping and its generation-level fitness history."""

    genome: Genome
    mse: float
    history: tuple[float, ...]
    evaluations: int


def _random_genome(
    rng: random.Random, input_names: Sequence[str], parameter_names: Sequence[str]
) -> Genome:
    inputs = list(input_names)
    parameters = list(parameter_names)
    rng.shuffle(inputs)
    rng.shuffle(parameters)
    return Genome(tuple(inputs), tuple(parameters))


def _order_crossover(
    rng: random.Random, left: tuple[str, ...], right: tuple[str, ...]
) -> tuple[str, ...]:
    if len(left) < _MIN_PERMUTATION_LENGTH:
        return left
    start, end = sorted(rng.sample(range(len(left)), 2))
    end += 1
    segment = left[start:end]
    remainder = [item for item in right if item not in segment]
    return tuple(remainder[:start] + list(segment) + remainder[start:])


def _mutate(rng: random.Random, genome: Genome) -> Genome:
    inputs = list(genome.inputs)
    parameters = list(genome.parameters)
    mutable = [group for group in (inputs, parameters) if len(group) > 1]
    if not mutable:
        return genome
    target = (
        mutable[0]
        if len(mutable) == 1 or rng.random() < _INPUT_MUTATION_PROBABILITY
        else mutable[1]
    )
    first, second = rng.sample(range(len(target)), 2)
    target[first], target[second] = target[second], target[first]
    return Genome(tuple(inputs), tuple(parameters))


def synthesize_mapping(
    input_names: Sequence[str],
    parameter_names: Sequence[str],
    fitness: Callable[[Genome], float],
    population_size: int = 400,
    generations: int = 10,
    seed: int = 7,
) -> SynthesisResult:
    """Search only well-typed permutation genomes, following the paper's CbC idea."""
    if population_size < _MIN_POPULATION:
        raise ValueError("population_size must be at least 4")
    if generations < 1:
        raise ValueError("generations must be at least 1")
    rng = random.Random(seed)
    population = [_random_genome(rng, input_names, parameter_names) for _ in range(population_size)]
    cache: dict[Genome, float] = {}
    history: list[float] = []
    best_genome = population[0]
    best_mse = float("inf")

    for _generation in range(generations):
        for genome in population:
            if genome not in cache:
                cache[genome] = fitness(genome)
        ranked = sorted(population, key=cache.__getitem__)
        if cache[ranked[0]] < best_mse:
            best_genome = ranked[0]
            best_mse = cache[ranked[0]]
        history.append(best_mse)
        if best_mse <= EXACT_MSE:
            break

        elite_count = max(2, population_size // 10)
        parent_pool = ranked[: max(4, population_size // 4)]
        next_population = ranked[:elite_count]
        while len(next_population) < population_size:
            left, right = rng.sample(parent_pool, 2)
            child = Genome(
                _order_crossover(rng, left.inputs, right.inputs),
                _order_crossover(rng, left.parameters, right.parameters),
            )
            if rng.random() < _MUTATION_PROBABILITY:
                child = _mutate(rng, child)
            next_population.append(child)
        population = next_population

    return SynthesisResult(best_genome, best_mse, tuple(history), len(cache))

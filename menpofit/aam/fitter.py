from __future__ import division
import numpy as np
from copy import deepcopy
from menpo.transform import AlignmentUniformScale
from menpo.image import BooleanImage
from menpofit.fitter import ModelFitter, noisy_shape_from_bounding_box
from menpofit.modelinstance import OrthoPDM
from menpofit.sdm import SupervisedDescentFitter
from menpofit.transform import OrthoMDTransform, LinearOrthoMDTransform
import menpofit.checks as checks
from .base import AAM, PatchAAM, LinearAAM, LinearPatchAAM, PartsAAM
from .algorithm.lk import (
    LucasKanadeStandardInterface, LucasKanadeLinearInterface,
    LucasKanadePartsInterface, WibergInverseCompositional)
from .algorithm.sd import (
    SupervisedDescentStandardInterface, SupervisedDescentLinearInterface,
    SupervisedDescentPartsInterface, ProjectOutNewton)
from .result import AAMFitterResult


# TODO: document me!
class AAMFitter(ModelFitter):
    r"""
    """
    @property
    def aam(self):
        return self._model

    def _check_n_appearance(self, n_appearance):
        checks.set_models_components(self.aam.appearance_models, n_appearance)

    def _fitter_result(self, image, algorithm_results, affine_correction,
                       gt_shape=None):
        return AAMFitterResult(image, self, algorithm_results,
                               affine_correction, gt_shape=gt_shape)


# TODO: document me!
class LucasKanadeAAMFitter(AAMFitter):
    r"""
    """
    def __init__(self, aam, lk_algorithm_cls=WibergInverseCompositional,
                 n_shape=None, n_appearance=None, sampling=None, **kwargs):
        self._model = aam
        self._check_n_shape(n_shape)
        self._check_n_appearance(n_appearance)
        sampling = checks.check_sampling(sampling, self.n_scales)
        self._set_up(lk_algorithm_cls, sampling, **kwargs)

    def _set_up(self, lk_algorithm_cls, sampling, **kwargs):
        self.algorithms = []
        for j, (am, sm, s) in enumerate(zip(self.aam.appearance_models,
                                            self.aam.shape_models, sampling)):

            if type(self.aam) is AAM or type(self.aam) is PatchAAM:
                # build orthonormal model driven transform
                md_transform = OrthoMDTransform(
                    sm, self.aam.transform,
                    source=am.mean().landmarks['source'].lms)
                # set up algorithm using standard aam interface
                algorithm = lk_algorithm_cls(
                    LucasKanadeStandardInterface, am, md_transform, sampling=s,
                    **kwargs)

            elif (type(self.aam) is LinearAAM or
                  type(self.aam) is LinearPatchAAM):
                # build linear version of orthogonal model driven transform
                md_transform = LinearOrthoMDTransform(
                    sm, self.aam.reference_shape)
                # set up algorithm using linear aam interface
                algorithm = lk_algorithm_cls(
                    LucasKanadeLinearInterface, am, md_transform, sampling=s,
                    **kwargs)

            elif type(self.aam) is PartsAAM:
                # build orthogonal point distribution model
                pdm = OrthoPDM(sm)
                # set up algorithm using parts aam interface
                algorithm = lk_algorithm_cls(
                    LucasKanadePartsInterface, am, pdm, sampling=s,
                    patch_shape=self.aam.patch_shape[j],
                    normalize_parts=self.aam.normalize_parts, **kwargs)

            else:
                raise ValueError("AAM object must be of one of the "
                                 "following classes: {}, {}, {}, {}, "
                                 "{}".format(AAM, PatchAAM, LinearAAM,
                                             LinearPatchAAM, PartsAAM))

            # append algorithms to list
            self.algorithms.append(algorithm)


# TODO: document me!
class SupervisedDescentAAMFitter(SupervisedDescentFitter):
    r"""
    """
    def __init__(self, images, aam, group=None, bounding_box_group=None,
                 n_shape=None, n_appearance=None, sampling=None,
                 sd_algorithm_cls=ProjectOutNewton,
                 n_iterations=6, n_perturbations=30,
                 perturb_from_bounding_box=noisy_shape_from_bounding_box,
                 batch_size=None, verbose=False):
        self.aam = aam
        checks.set_models_components(aam.appearance_models, n_appearance)
        checks.set_models_components(aam.shape_models, n_shape)
        self._sampling = checks.check_sampling(sampling, aam.n_scales)

        # patch_feature and patch_shape are not actually
        # used because they are fully defined by the AAM already. Therefore,
        # we just leave them as their 'defaults' because they won't be used.
        super(SupervisedDescentAAMFitter, self).__init__(
            images, group=group, bounding_box_group=bounding_box_group,
            reference_shape=self.aam.reference_shape,
            sd_algorithm_cls=sd_algorithm_cls,
            holistic_feature=self.aam.features,
            diagonal=self.aam.diagonal,
            scales=self.aam.scales, n_iterations=n_iterations,
            n_perturbations=n_perturbations,
            perturb_from_bounding_box=perturb_from_bounding_box,
            batch_size=batch_size, verbose=verbose)

    def _setup_algorithms(self):
        self.algorithms = []
        for j, (am, sm, s) in enumerate(zip(self.aam.appearance_models,
                                            self.aam.shape_models,
                                            self._sampling)):

            if type(self.aam) is AAM or type(self.aam) is PatchAAM:
                # build orthonormal model driven transform
                md_transform = OrthoMDTransform(
                    sm, self.aam.transform,
                    source=am.mean().landmarks['source'].lms)
                # set up algorithm using standard aam interface
                algorithm = self._sd_algorithm_cls(
                    SupervisedDescentStandardInterface, am, md_transform,
                    sampling=s, max_iters=self.n_iterations[j])

            elif (type(self.aam) is LinearAAM or
                  type(self.aam) is LinearPatchAAM):
                # build linear version of orthogonal model driven transform
                md_transform = LinearOrthoMDTransform(
                    sm, self.aam.reference_shape)
                # set up algorithm using linear aam interface
                algorithm = self._sd_algorithm_cls(
                    SupervisedDescentLinearInterface, am, md_transform,
                    sampling=s, max_iters=self.n_iterations[j])

            elif type(self.aam) is PartsAAM:
                # build orthogonal point distribution model
                pdm = OrthoPDM(sm)
                # set up algorithm using parts aam interface
                algorithm = self._sd_algorithm_cls(
                    SupervisedDescentPartsInterface, am, pdm,
                    sampling=s, max_iters=self.n_iterations[j],
                    patch_shape=self.aam.patch_shape[j],
                    normalize_parts=self.aam.normalize_parts)

            else:
                raise ValueError("AAM object must be of one of the "
                                 "following classes: {}, {}, {}, {}, "
                                 "{}".format(AAM, PatchAAM, LinearAAM,
                                             LinearPatchAAM, PartsAAM))

            # append algorithms to list
            self.algorithms.append(algorithm)


# TODO: Document me!
def holistic_sampling_from_scale(aam, scale=0.35):
    reference = aam.appearance_models[0].mean()
    scaled_reference = reference.rescale(scale)

    t = AlignmentUniformScale(scaled_reference.landmarks['source'].lms,
                              reference.landmarks['source'].lms)
    new_indices = np.require(np.round(t.apply(
        scaled_reference.mask.true_indices())), dtype=np.int)

    modified_mask = deepcopy(reference.mask.pixels)
    modified_mask[:] = False
    modified_mask[:, new_indices[:, 0], new_indices[:, 1]] = True

    true_positions = np.nonzero(
        modified_mask[:, reference.mask.mask].ravel())[0]

    return true_positions, BooleanImage(modified_mask[0])


# TODO: Document me!
def holistic_sampling_from_step(aam, step=8):
    reference = aam.appearance_models[0].mean()

    n_true_pixels = reference.n_true_pixels()
    true_positions = np.zeros(n_true_pixels, dtype=np.bool)
    sampling = xrange(0, n_true_pixels, step)
    true_positions[sampling] = True

    modified_mask = reference.mask.copy()
    new_indices = modified_mask.true_indices()[sampling, :]
    modified_mask.mask[:] = False
    modified_mask.mask[new_indices[:, 0], new_indices[:, 1]] = True

    return true_positions, modified_mask

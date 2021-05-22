import jax.numpy as jnp
import flax.linen as nn
import functools
from typing import (Any, Callable, Iterable, Optional, Tuple, Union)
import h5py
from . import ops
from .. import utils


URLS = {'resnet18': 'https://www.dropbox.com/s/wx3vt76s5gpdcw5/resnet18_weights.h5?dl=1',
        'resnet34': 'https://www.dropbox.com/s/rnqn2x6trnztg4c/resnet34_weights.h5?dl=1',
        'resnet50': 'https://www.dropbox.com/s/fcc8iii38ezvqog/resnet50_weights.h5?dl=1',
        'resnet101': 'https://www.dropbox.com/s/hgtnk586pnz0xug/resnet101_weights.h5?dl=1',
        'resnet152': 'https://www.dropbox.com/s/tvi28uwiy54mcfr/resnet152_weights.h5?dl=1'}

LAYERS = {'resnet18': [2, 2, 2, 2],
          'resnet34': [3, 4, 6, 3],
          'resnet50': [3, 4, 6, 3],
          'resnet101': [3, 4, 23, 3],
          'resnet152': [3, 8, 36, 3]}


class BasicBlock(nn.Module):
    """
    Basic Block.

    Attributes:
        features (int): Number of output channels.
        kernel_size (Tuple): Kernel size.
        downsample (bool): If True, downsample spatial resolution.
        stride (bool): If True, use strides (2, 2). Not used in this module.
                       The attribute is only here for compatibility with Bottleneck.
        train (bool): If True, use training mode.
        param_dict (h5py.Group): Parameter dict with pretrained parameters.
        kernel_init (functools.partial): Kernel initializer.
        bias_init (functools.partial): Bias initializer.
        block_name (str): Name of block.
    """
    features: int
    kernel_size: Union[int, Iterable[int]] = (3, 3)
    downsample: bool = False
    stride: bool = True
    train: bool = False
    param_dict: h5py.Group = None
    kernel_init: functools.partial = nn.initializers.lecun_normal()
    bias_init: functools.partial = nn.initializers.zeros
    block_name: str = None

    @nn.compact
    def __call__(self, x, act):
        """
        Run Basic Block.

        Args:
            x (tensor): Input tensor of shape [N, H, W, C].
            act (dict): Dictionary containing activations.

        Returns:
            (tensor): Output shape of shape [N, H', W', features].
        """
        residual = x 
        
        x = nn.Conv(features=self.features, 
                    kernel_size=self.kernel_size, 
                    strides=(2, 2) if self.downsample else (1, 1),
                    padding=((1, 1), (1, 1)),
                    kernel_init=self.kernel_init if self.param_dict is None else lambda *_ : jnp.array(self.param_dict['conv1']['weight']), 
                    use_bias=False)(x)

        x = ops.batch_norm(x, train=self.train, epsilon=1e-05, momentum=0.1, params=None if self.train else self.param_dict['bn1']) 
        x = nn.relu(x)

        x = nn.Conv(features=self.features, 
                    kernel_size=self.kernel_size, 
                    strides=(1, 1), 
                    padding=((1, 1), (1, 1)),
                    kernel_init=self.kernel_init if self.param_dict is None else lambda *_ : jnp.array(self.param_dict['conv2']['weight']), 
                    use_bias=False)(x)

        x = ops.batch_norm(x, train=self.train, epsilon=1e-05, momentum=0.1, params=None if self.train else self.param_dict['bn2']) 

        if self.downsample:
            residual = nn.Conv(features=self.features, 
                               kernel_size=(1, 1), 
                               strides=(2, 2), 
                               kernel_init=self.kernel_init if self.param_dict is None else lambda *_ : jnp.array(self.param_dict['downsample']['conv']['weight']), 
                               use_bias=False)(residual)

            residual = ops.batch_norm(residual, train=self.train, epsilon=1e-05, momentum=0.1, params=None if self.train else self.param_dict['downsample']['bn']) 
        
        x += residual
        x = nn.relu(x)
        act[self.block_name] = x
        return x


class Bottleneck(nn.Module):
    """
    Bottleneck.

    Attributes:
        features (int): Number of output channels.
        kernel_size (Tuple): Kernel size.
        downsample (bool): If True, downsample spatial resolution.
        stride (bool): If True, use strides (2, 2). Not used in this module.
                       The attribute is only here for compatibility with Bottleneck.
        train (bool): If True, use training mode.
        param_dict (h5py.Group): Parameter dict with pretrained parameters.
        kernel_init (functools.partial): Kernel initializer.
        bias_init (functools.partial): Bias initializer.
        block_name (str): Name of block.
        expansion (int): Factor to multiply number of output channels with.
    """
    features: int
    kernel_size: Union[int, Iterable[int]] = (3, 3)
    downsample: bool = False
    stride: bool = True
    train: bool = False
    param_dict: Any = None
    kernel_init: functools.partial = nn.initializers.lecun_normal()
    bias_init: functools.partial = nn.initializers.zeros
    block_name: str = None
    expansion: int = 4

    @nn.compact
    def __call__(self, x, act):
        """
        Run Bottleneck.

        Args:
            x (tensor): Input tensor of shape [N, H, W, C].
            act (dict): Dictionary containing activations.

        Returns:
            (tensor): Output shape of shape [N, H', W', features].
        """
        residual = x 
        
        x = nn.Conv(features=self.features, 
                    kernel_size=(1, 1), 
                    strides=(1, 1),
                    kernel_init=self.kernel_init if self.param_dict is None else lambda *_ : jnp.array(self.param_dict['conv1']['weight']), 
                    use_bias=False)(x)

        x = ops.batch_norm(x, train=self.train, epsilon=1e-05, momentum=0.1, params=None if self.train else self.param_dict['bn1']) 
        x = nn.relu(x)

        x = nn.Conv(features=self.features, 
                    kernel_size=(3, 3), 
                    strides=(2, 2) if self.downsample and self.stride else (1, 1), 
                    padding=((1, 1), (1, 1)),
                    kernel_init=self.kernel_init if self.param_dict is None else lambda *_ : jnp.array(self.param_dict['conv2']['weight']), 
                    use_bias=False)(x)
        
        x = ops.batch_norm(x, train=self.train, epsilon=1e-05, momentum=0.1, params=None if self.train else self.param_dict['bn2']) 
        x = nn.relu(x)

        x = nn.Conv(features=self.features * self.expansion, 
                    kernel_size=(1, 1), 
                    strides=(1, 1), 
                    kernel_init=self.kernel_init if self.param_dict is None else lambda *_ : jnp.array(self.param_dict['conv3']['weight']), 
                    use_bias=False)(x)

        x = ops.batch_norm(x, train=self.train, epsilon=1e-05, momentum=0.1, params=None if self.train else self.param_dict['bn3']) 

        if self.downsample:
            residual = nn.Conv(features=self.features * self.expansion, 
                               kernel_size=(1, 1), 
                               strides=(2, 2) if self.stride else (1, 1), 
                               kernel_init=self.kernel_init if self.param_dict is None else lambda *_ : jnp.array(self.param_dict['downsample']['conv']['weight']), 
                               use_bias=False)(residual)

            residual = ops.batch_norm(residual, train=self.train, epsilon=1e-05, momentum=0.1, params=None if self.train else self.param_dict['downsample']['bn']) 
        
        x += residual
        x = nn.relu(x)
        act[self.block_name] = x
        return x


class ResNet(nn.Module):
    """
    ResNet.

    Attributes:
        output (str):
            Output of the module. Available options are:
                - 'softmax': Output is a softmax tensor of shape [N, 1000] 
                - 'logits': Output is a tensor of shape [N, 1000]
                - 'activations': Output is a dictionary containing the ResNet activations
        pretrained (str):
            Indicates if and what type of weights to load. Options are:
                - 'imagenet': Loads the network parameters trained on ImageNet
                - None: Parameters of the module are initialized randomly
        architecture (str): 
            Which ResNet model to use:
                - 'resnet18'
                - 'resnet34'
                - 'resnet50'
                - 'resnet101'
                - 'resnet152'
        block (nn.Module):
            Type of residual block:
                - BasicBlock
                - Bottleneck
        kernel_init (function):
            A function that takes in a shape and returns a tensor.
        bias_init (function):
            A function that takes in a shape and returns a tensor.
        ckpt_dir (str):
            The directory to which the pretrained weights are downloaded.
            Only relevant if a pretrained model is used. 
            If this argument is None, the weights will be saved to a temp directory.
    """
    output: str='softmax'
    pretrained: str='imagenet'
    architecture: str='resnet18'
    block: nn.Module=BasicBlock
    kernel_init: functools.partial=nn.initializers.lecun_normal()
    bias_init: functools.partial=nn.initializers.zeros
    ckpt_dir: str=None

    def setup(self):
        if self.pretrained == 'imagenet':
            ckpt_file = utils.download(self.ckpt_dir, URLS[self.architecture])
            self.param_dict = h5py.File(ckpt_file, 'r')

    @nn.compact
    def __call__(self, x):
        """
        Args:
            x (tensor): Input tensor of shape [N, H, W, 3]. Images must be in range [0, 1].

        Returns:
            (tensor): Out
            If output == 'logits' or output == 'softmax':
                (tensor): Output tensor of shape [N, num_classes].
            If output == 'activations':
                (dict): Dictionary of activations.
        """     
        if self.pretrained == 'imagenet':
            # normalize input
            mean = jnp.array([0.485, 0.456, 0.406]).reshape(1, 1, 1, -1)
            std = jnp.array([0.229, 0.224, 0.225]).reshape(1, 1, 1, -1)
            x = (x - mean) / std
 
        act = {}

        train = self.pretrained is None

        x = nn.Conv(features=64, 
                    kernel_size=(7, 7),
                    kernel_init=self.kernel_init if train else lambda *_ : jnp.array(self.param_dict['conv1']['weight']),
                    strides=(2, 2), 
                    padding=((3, 3), (3, 3)),
                    use_bias=False)(x)
        act['conv1'] = x

        x = ops.batch_norm(x, train=train, epsilon=1e-05, momentum=0.1, params=None if train else self.param_dict['bn1'])
        x = nn.relu(x)
        x = nn.max_pool(x, window_shape=(3, 3), strides=(2, 2), padding=((1, 1), (1, 1)))

        # Layer 1
        down = self.block.__name__ == 'Bottleneck'
        for i in range(LAYERS[self.architecture][0]):
            params = None if train else self.param_dict['layer1'][f'block{i}']
            x = self.block(features=64, kernel_size=(3, 3), downsample=i == 0 and down, stride=i != 0, train=train, param_dict=params, block_name=f'block1_{i}')(x, act)
        
        # Layer 2
        for i in range(LAYERS[self.architecture][1]):
            params = None if train else self.param_dict['layer2'][f'block{i}']
            x = self.block(features=128, kernel_size=(3, 3), downsample=i == 0, train=train, param_dict=params, block_name=f'block2_{i}')(x, act)
        
        # Layer 3
        for i in range(LAYERS[self.architecture][2]):
            params = None if train else self.param_dict['layer3'][f'block{i}']
            x = self.block(features=256, kernel_size=(3, 3), downsample=i == 0, train=train, param_dict=params, block_name=f'block3_{i}')(x, act)

        # Layer 4
        for i in range(LAYERS[self.architecture][3]):
            params = None if train else self.param_dict['layer4'][f'block{i}']
            x = self.block(features=512, kernel_size=(3, 3), downsample=i == 0, train=train, param_dict=params, block_name=f'block4_{i}')(x, act)

        # Classifier
        x = jnp.mean(x, axis=(1, 2))
        x = nn.Dense(features=1000, 
                     kernel_init=self.kernel_init if train else lambda *_ : jnp.array(self.param_dict['fc']['weight']), 
                     bias_init=self.bias_init if train else lambda *_ : jnp.array(self.param_dict['fc']['bias']))(x)
        act['fc'] = x
        
        if self.output == 'softmax':
            return nn.softmax(x)
        if self.output == 'activations':
            return act 
        return x


def ResNet18(output='softmax', 
             pretrained='imagenet', 
             kernel_init=nn.initializers.lecun_normal(), 
             bias_init=nn.initializers.zeros,
             ckpt_dir=None):
    """
    Implementation of the ResNet18 by He et al.
    Reference: https://arxiv.org/abs/1512.03385

    The pretrained parameters are taken from:
    https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py
    
    Args:
        output (str):
            Output of the module. Available options are:
                - 'softmax': Output is a softmax tensor of shape [N, 1000] 
                - 'logits': Output is a tensor of shape [N, 1000]
                - 'activations': Output is a dictionary containing the ResNet activations
        pretrained (str):
            Indicates if and what type of weights to load. Options are:
                - 'imagenet': Loads the network parameters trained on ImageNet
                - None: Parameters of the module are initialized randomly
        kernel_init (function):
            A function that takes in a shape and returns a tensor.
        bias_init (function):
            A function that takes in a shape and returns a tensor.
        ckpt_dir (str):
            The directory to which the pretrained weights are downloaded.
            Only relevant if a pretrained model is used. 
            If this argument is None, the weights will be saved to a temp directory.

    Returns:
        (nn.Module): ResNet network.
    """
    return ResNet(output=output,
                  pretrained=pretrained,
                  architecture='resnet18',
                  block=BasicBlock,
                  kernel_init=kernel_init,
                  bias_init=bias_init,
                  ckpt_dir=ckpt_dir)


def ResNet34(output='softmax', 
             pretrained='imagenet', 
             kernel_init=nn.initializers.lecun_normal(), 
             bias_init=nn.initializers.zeros,
             ckpt_dir=None):
    """
    Implementation of the ResNet34 by He et al.
    Reference: https://arxiv.org/abs/1512.03385

    The pretrained parameters are taken from:
    https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py
    
    Args:
        output (str):
            Output of the module. Available options are:
                - 'softmax': Output is a softmax tensor of shape [N, 1000] 
                - 'logits': Output is a tensor of shape [N, 1000]
                - 'activations': Output is a dictionary containing the ResNet activations
        pretrained (str):
            Indicates if and what type of weights to load. Options are:
                - 'imagenet': Loads the network parameters trained on ImageNet
                - None: Parameters of the module are initialized randomly
        kernel_init (function):
            A function that takes in a shape and returns a tensor.
        bias_init (function):
            A function that takes in a shape and returns a tensor.
        ckpt_dir (str):
            The directory to which the pretrained weights are downloaded.
            Only relevant if a pretrained model is used. 
            If this argument is None, the weights will be saved to a temp directory.

    Returns:
        (nn.Module): ResNet network.
    """
    return ResNet(output=output,
                  pretrained=pretrained,
                  architecture='resnet34',
                  block=BasicBlock,
                  kernel_init=kernel_init,
                  bias_init=bias_init,
                  ckpt_dir=ckpt_dir)


def ResNet50(output='softmax', 
             pretrained='imagenet', 
             kernel_init=nn.initializers.lecun_normal(), 
             bias_init=nn.initializers.zeros,
             ckpt_dir=None):
    """
    Implementation of the ResNet50 by He et al.
    Reference: https://arxiv.org/abs/1512.03385

    The pretrained parameters are taken from:
    https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py
    
    Args:
        output (str):
            Output of the module. Available options are:
                - 'softmax': Output is a softmax tensor of shape [N, 1000] 
                - 'logits': Output is a tensor of shape [N, 1000]
                - 'activations': Output is a dictionary containing the ResNet activations
        pretrained (str):
            Indicates if and what type of weights to load. Options are:
                - 'imagenet': Loads the network parameters trained on ImageNet
                - None: Parameters of the module are initialized randomly
        kernel_init (function):
            A function that takes in a shape and returns a tensor.
        bias_init (function):
            A function that takes in a shape and returns a tensor.
        ckpt_dir (str):
            The directory to which the pretrained weights are downloaded.
            Only relevant if a pretrained model is used. 
            If this argument is None, the weights will be saved to a temp directory.

    Returns:
        (nn.Module): ResNet network.
    """
    return ResNet(output=output,
                  pretrained=pretrained,
                  architecture='resnet50',
                  block=Bottleneck,
                  kernel_init=kernel_init,
                  bias_init=bias_init,
                  ckpt_dir=ckpt_dir)


def ResNet101(output='softmax', 
              pretrained='imagenet', 
              kernel_init=nn.initializers.lecun_normal(), 
              bias_init=nn.initializers.zeros,
              ckpt_dir=None):
    """
    Implementation of the ResNet101 by He et al.
    Reference: https://arxiv.org/abs/1512.03385

    The pretrained parameters are taken from:
    https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py
    
    Args:
        output (str):
            Output of the module. Available options are:
                - 'softmax': Output is a softmax tensor of shape [N, 1000] 
                - 'logits': Output is a tensor of shape [N, 1000]
                - 'activations': Output is a dictionary containing the ResNet activations
        pretrained (str):
            Indicates if and what type of weights to load. Options are:
                - 'imagenet': Loads the network parameters trained on ImageNet
                - None: Parameters of the module are initialized randomly
        kernel_init (function):
            A function that takes in a shape and returns a tensor.
        bias_init (function):
            A function that takes in a shape and returns a tensor.
        ckpt_dir (str):
            The directory to which the pretrained weights are downloaded.
            Only relevant if a pretrained model is used. 
            If this argument is None, the weights will be saved to a temp directory.

    Returns:
        (nn.Module): ResNet network.
    """
    return ResNet(output=output,
                  pretrained=pretrained,
                  architecture='resnet101',
                  block=Bottleneck,
                  kernel_init=kernel_init,
                  bias_init=bias_init,
                  ckpt_dir=ckpt_dir)


def ResNet152(output='softmax', 
              pretrained='imagenet', 
              kernel_init=nn.initializers.lecun_normal(), 
              bias_init=nn.initializers.zeros,
              ckpt_dir=None):
    """
    Implementation of the ResNet152 by He et al.
    Reference: https://arxiv.org/abs/1512.03385

    The pretrained parameters are taken from:
    https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py
    
    Args:
        output (str):
            Output of the module. Available options are:
                - 'softmax': Output is a softmax tensor of shape [N, 1000] 
                - 'logits': Output is a tensor of shape [N, 1000]
                - 'activations': Output is a dictionary containing the ResNet activations
        pretrained (str):
            Indicates if and what type of weights to load. Options are:
                - 'imagenet': Loads the network parameters trained on ImageNet
                - None: Parameters of the module are initialized randomly
        kernel_init (function):
            A function that takes in a shape and returns a tensor.
        bias_init (function):
            A function that takes in a shape and returns a tensor.
        ckpt_dir (str):
            The directory to which the pretrained weights are downloaded.
            Only relevant if a pretrained model is used. 
            If this argument is None, the weights will be saved to a temp directory.

    Returns:
        (nn.Module): ResNet network.
    """
    return ResNet(output=output,
                  pretrained=pretrained,
                  architecture='resnet152',
                  block=Bottleneck,
                  kernel_init=kernel_init,
                  bias_init=bias_init,
                  ckpt_dir=ckpt_dir)


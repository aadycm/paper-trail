---
id: layernorm2016
title: Layer Normalization
authors: Ba, Kiros, Hinton
year: 2016
cites: batchnorm2015
---
We propose normalising across features within a single example, which removes
the dependence on batch size. This improves training time for recurrent
networks, where [[batchnorm2015]] cannot be applied straightforwardly.

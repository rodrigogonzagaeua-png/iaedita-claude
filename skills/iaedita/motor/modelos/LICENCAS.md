# Modelos incluídos

## face_detection_yunet_2023mar.onnx — achar o rosto
YuNet (OpenCV Zoo), https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
Licença MIT:

MIT License

Copyright (c) 2020 Shiqi Yu <shiqi.yu@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## voz_rnnoise.rnnn — modelo incluído e desligado
Modelo padrão do RNNoise (Xiph), usado pelo filtro `arnndn` do FFmpeg.
Licença BSD-3-Clause:

Copyright (c) 2017, Mozilla
Copyright (c) 2007-2017, Jean-Marc Valin
Copyright (c) 2005-2017, Xiph.Org Foundation
Copyright (c) 2003-2004, Mark Borgerding

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

- Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.

- Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

- Neither the name of the Xiph.Org Foundation nor the names of its
contributors may be used to endorse or promote products derived from
this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION
OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Modelos baixados no uso

Não vêm no pacote. Cada um é baixado da origem indicada na primeira vez que for preciso. Origem e licença conforme o repositório de cada projeto, conferidos em 02/11/2026.

## Transcrição: Systran/faster-whisper-small
- Origem: https://huggingface.co/Systran/faster-whisper-small
- Licença: MIT, declarada na página do modelo.

## Recorte da pessoa: rvm_mobilenetv3_fp32.onnx
- Projeto: RobustVideoMatting, repositório PeterL1n/RobustVideoMatting.
- Origem: https://github.com/PeterL1n/RobustVideoMatting/releases
- Licença: GPL-3.0, no arquivo LICENSE do repositório (https://github.com/PeterL1n/RobustVideoMatting/blob/master/LICENSE).

## Reforço do corpo: u2net_human_seg.onnx (com a opção `--reforco` de `recortar`, que o manual não usa, ou pela biblioteca rembg, se já estiver no ambiente)
- Projeto: U-2-Net, repositório xuebinqin/U-2-Net, cuja página descreve o modelo de pessoas `u2net_human_seg`.
- Origem do arquivo: https://github.com/danielgatis/rembg/releases , na versão chamada Models. O repositório danielgatis/rembg traz licença MIT.
- Licença: Apache-2.0, no arquivo LICENSE do repositório xuebinqin/U-2-Net. Não foi confirmada uma licença própria para este arquivo `.onnx`: a página da versão Models não declara nenhuma.

## Caminho raro: modelo do openai-whisper (só se a biblioteca já estiver no ambiente)
- Origem: baixado pela própria biblioteca, repositório openai/whisper.
- Licença: MIT. O README do repositório diz que o código e os pesos do modelo seguem a licença MIT.

"""Autorização online vinculada ao original e a uma chave privada deste executor.

O protocolo devolve apenas dados públicos ao agente. A chave nunca sai desta pasta
local; toda operação de edição confere o acesso atual via HTTPS, sem cache permissivo.
"""
from __future__ import annotations

import base64
import contextvars
import errno
import hashlib
import http.client
import json
import os
import re
import secrets
import socket
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

ORIGEM = 'https://editor-rg.santosperesraquel4.workers.dev'
_TTL = 600000
_OPERACAO = contextvars.ContextVar('iaedita_operacao_autorizada', default=None)
_DIAGNOSTICOS = {
    'AUTORIZACAO_NAO_CONFIRMADA': 'autorizacao',
    'AUTORIZACAO_EXPIRADA': 'autorizacao',
    'AUTORIZACAO_CONFIRMACAO_EXPIRADA': 'autorizacao',
    'AUTORIZACAO_DNS': 'comunicacao',
    'AUTORIZACAO_TIMEOUT': 'comunicacao',
    'AUTORIZACAO_TLS_CERTIFICADO': 'comunicacao',
    'AUTORIZACAO_TLS': 'comunicacao',
    'AUTORIZACAO_PERMISSAO_LOCAL': 'comunicacao',
    'AUTORIZACAO_TRANSPORTE': 'comunicacao',
    'AUTORIZACAO_REDE_RESTRITA': 'comunicacao',
    'AUTORIZACAO_HTTP': 'http',
    'AUTORIZACAO_JSON_INVALIDO': 'resposta',
}
_REDE_RESTRITA = 'A rede do ambiente bloqueou a conexão com o servidor de autorização. Repetir não resolve enquanto a rede não for liberada.'
_TUNEL_NEGADO = re.compile(r'Tunnel connection failed: (403|407)\b')  # texto do http.client quando o intermediário nega o túnel


class ErroLicenca(RuntimeError):
    """Mensagem segura para o usuário, sem material de chave ou resposta remota."""

    def __init__(self, mensagem, *, codigo='AUTORIZACAO_NAO_CONFIRMADA', http_status=None):
        super().__init__(mensagem)
        self._codigo = codigo if isinstance(codigo, str) and codigo in _DIAGNOSTICOS else 'AUTORIZACAO_NAO_CONFIRMADA'
        self._http_status = (http_status if self._codigo == 'AUTORIZACAO_HTTP'
                             and type(http_status) is int and 100 <= http_status <= 599 else None)

    @property
    def diagnostico(self):
        """Somente campos permitidos; nunca inclui texto da exceção de transporte."""
        result = {'codigo': self._codigo, 'categoria': _DIAGNOSTICOS[self._codigo]}
        if self._http_status is not None:
            result['http_status'] = self._http_status
        return result


def _erro_comunicacao(error):
    # urllib costuma envolver a exceção real em reason. Não interpretar texto livre, só a negativa do túnel.
    for _ in range(5):
        if not isinstance(error, urllib.error.URLError) or not isinstance(error.reason, BaseException):
            break
        error = error.reason
    if isinstance(error, OSError) and _TUNEL_NEGADO.search(str(error)):
        return ErroLicenca(_REDE_RESTRITA, codigo='AUTORIZACAO_REDE_RESTRITA')
    if isinstance(error, socket.gaierror):
        codigo = 'AUTORIZACAO_DNS'
    elif isinstance(error, ssl.SSLCertVerificationError):
        codigo = 'AUTORIZACAO_TLS_CERTIFICADO'
    elif isinstance(error, ssl.SSLError):
        codigo = 'AUTORIZACAO_TLS'
    elif isinstance(error, TimeoutError):
        codigo = 'AUTORIZACAO_TIMEOUT'
    elif isinstance(error, PermissionError) or (isinstance(error, OSError) and error.errno in (errno.EACCES, errno.EPERM)):
        codigo = 'AUTORIZACAO_PERMISSAO_LOCAL'
    else:
        codigo = 'AUTORIZACAO_TRANSPORTE'
    return ErroLicenca('Não foi possível conferir seu acesso pela internet. Preserve o projeto e tente novamente mais tarde.', codigo=codigo)


def _crypto():
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        return hashes, serialization, ec, utils
    except ImportError:
        raise ErroLicenca('Falta o componente de autorização. Instale cryptography e prepare a autorização novamente.') from None


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _b64(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _hash(video):
    try:
        with Path(video).open('rb') as handle:
            return hashlib.file_digest(handle, 'sha256').hexdigest()
    except OSError:
        raise ErroLicenca('Não foi possível ler o vídeo original. Confira o arquivo antes de autorizar.') from None


def _atomic(path, contents):
    descriptor, temp = tempfile.mkstemp(prefix='.gravando-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _local(pasta):
    return Path(pasta).resolve() / '.iaedita'


def _estado(pasta):
    try:
        value = json.loads((_local(pasta) / 'estado.json').read_text(encoding='utf-8'))
        if not isinstance(value, dict) or value.get('pasta') != str(Path(pasta).resolve()):
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError):
        raise ErroLicenca('Prepare a autorização deste vídeo nesta pasta e autorize a edição pela sua conta IAEdita.') from None


def _salvar(pasta, value):
    _atomic(_local(pasta) / 'estado.json', _json(value).encode('utf-8'))


def _chave(pasta):
    _, serialization, ec, _ = _crypto()
    try:
        key = serialization.load_pem_private_key((_local(pasta) / 'chave.pem').read_bytes(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
            raise ValueError()
        return key
    except (OSError, ValueError, TypeError):
        raise ErroLicenca('A chave local de autorização não está disponível. Prepare uma nova autorização nesta pasta.') from None


def _publica(key):
    numbers = key.public_key().public_numbers()
    return {'kty': 'EC', 'crv': 'P-256', 'x': _b64(numbers.x.to_bytes(32, 'big')), 'y': _b64(numbers.y.to_bytes(32, 'big'))}


def preparar_autorizacao(video, pasta):
    """Gera a chave local e devolve somente o pedido público destinado ao MCP."""
    _, serialization, ec, _ = _crypto()
    original = str(Path(video).resolve())
    arquivo_hash = _hash(original)
    directory = _local(pasta)
    if directory.is_symlink() or (hasattr(directory, 'is_junction') and directory.is_junction()):
        raise ErroLicenca('Use uma pasta de trabalho local para a autorização.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        state = _estado(pasta)
        key = _chave(pasta)
        if state.get('original') != original or state.get('arquivo_sha256') != arquivo_hash:
            raise ErroLicenca('O original mudou.')
    except ErroLicenca:
        key = ec.generate_private_key(ec.SECP256R1())
        state = {'pasta': str(Path(pasta).resolve()), 'original': original, 'arquivo_sha256': arquivo_hash, 'projeto': str(uuid.uuid4())}
        _atomic(directory / 'chave.pem', key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        _salvar(pasta, state)
    return {'projeto': state['projeto'], 'arquivo_sha256': arquivo_hash, 'chave_publica': _publica(key)}


def _conferir_original(pasta, state, video=None):
    if _hash(state.get('original', '')) != state.get('arquivo_sha256'):
        raise ErroLicenca('O vídeo original mudou após a autorização. Prepare uma nova autorização para este arquivo.')
    if video is not None and str(Path(video).resolve()) != state.get('original'):
        raise ErroLicenca('Este vídeo não corresponde à autorização. Prepare uma autorização para o original correto.')
    if video is not None:
        return  # preparar/analisar recebem explicitamente a fonte e podem substituir análise antiga.
    analyses = [Path(pasta) / 'analise.json']
    versions = Path(pasta) / '_versoes'
    for version in ('original', 'editado', 'sem_silencio'):
        folder = versions / version
        analyses.append(folder / 'analise.json')
        progress = folder / '_silencio_partes'
        if progress.exists():
            _conferir_progresso(pasta, state, progress)
        # Um arquivo final já existente sem registro não pode virar derivada por mera retomada.
        for cached in folder.glob('video_*.mkv'):
            _conferir_video(pasta, state, cached)
    for analysis_path in analyses:
        if not analysis_path.exists():
            continue
        try:
            analysis = json.loads(analysis_path.read_text(encoding='utf-8'))
            if analysis.get('video_original') and str(Path(analysis['video_original']).resolve()) != state['original']:
                raise ValueError()
            actual_video = analysis['video']
        except (OSError, ValueError, TypeError, KeyError):
            raise ErroLicenca('A análise pertence a outro vídeo. Prepare a autorização do original correto.') from None
        _conferir_video(pasta, state, actual_video)


def _vinculo_derivada(state, video, arquivo_hash):
    return _json(['iaedita-derivada-v1', state['projeto'], state['sessao']['usuario_id'], state['original'],
                  state['arquivo_sha256'], str(Path(video).resolve()), arquivo_hash]).encode('utf-8')


def _assinar_local(pasta, message):
    hashes, _, ec, utils = _crypto()
    signature = _chave(pasta).sign(message, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(signature)
    return _b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))


def _verificar_local(pasta, message, assinatura):
    hashes, _, ec, utils = _crypto()
    signature = base64.b64decode(assinatura + '==', altchars=b'-_', validate=True)
    if len(signature) != 64:
        raise ValueError()
    der = utils.encode_dss_signature(int.from_bytes(signature[:32], 'big'), int.from_bytes(signature[32:], 'big'))
    _chave(pasta).public_key().verify(der, message, ec.ECDSA(hashes.SHA256()))


def _arquivos_progresso(folder):
    folder = Path(folder)
    files = []
    for item in sorted(folder.iterdir()):
        if not item.is_file() or item.resolve().parent != folder.resolve():
            raise ValueError()
        files.append([item.name, _hash(item)])
    return files


def _vinculo_progresso(state, folder, arquivos):
    return _json(['iaedita-progresso-v1', state['projeto'], state['sessao']['usuario_id'], state['original'],
                  state['arquivo_sha256'], str(Path(folder).resolve()), arquivos]).encode('utf-8')


def _conferir_progresso(pasta, state, folder):
    try:
        proof = state.get('progresso', {})[str(folder.resolve())]
        arquivos = _arquivos_progresso(folder)
        _verificar_local(pasta, _vinculo_progresso(state, folder, arquivos), proof['assinatura'])
    except Exception:
        raise ErroLicenca('Os pedaços de retomada não têm origem autorizada comprovada. Preserve o original e refaça a edição em uma pasta nova.') from None


def _conferir_video(pasta, state, video):
    actual = str(Path(video).resolve())
    if actual == state['original']:
        return  # O hash do original já foi conferido nesta operação.
    try:
        proof = state.get('derivadas', {})[actual]
        if _hash(actual) != proof['arquivo_sha256']:
            raise ValueError()
        _verificar_local(pasta, _vinculo_derivada(state, actual, proof['arquivo_sha256']), proof['assinatura'])
    except Exception:
        raise ErroLicenca('Este vídeo não possui uma origem autorizada comprovada. Preserve o original e refaça a edição em uma pasta nova; não reutilize esta derivada.') from None


def _destino_derivada(pasta, origem, video):
    context = _OPERACAO.get()
    state = _estado(pasta)
    expected = (str(Path(pasta).resolve()), state['projeto'], state['arquivo_sha256'])
    if not context or context[:3] != expected or context[3] <= int(time.time() * 1000):
        raise ErroLicenca('A criação da versão editada não foi autorizada nesta execução.')
    _conferir_original(pasta, state, origem)
    target = Path(video).resolve()
    versions = Path(pasta).resolve() / '_versoes'
    if target.parent not in (versions / 'editado', versions / 'sem_silencio') or target.suffix != '.mkv' or not target.name.startswith('video_'):
        raise ErroLicenca('O arquivo produzido está fora da pasta de versões deste projeto.')
    return state, target


def registrar_derivada(pasta, origem, video):
    """Chamado somente após o montador real concluir, dentro de uma operação autorizada."""
    state, target = _destino_derivada(pasta, origem, video)
    arquivo_hash = _hash(target)
    state.setdefault('derivadas', {})[str(target)] = {'arquivo_sha256': arquivo_hash,
        'assinatura': _assinar_local(pasta, _vinculo_derivada(state, target, arquivo_hash))}
    _salvar(pasta, state)


def registrar_progresso(pasta, origem, video):
    """Atesta os pedaços e o estado retornados pelo montador real para a próxima etapa."""
    state, target = _destino_derivada(pasta, origem, video)
    folder = target.parent / '_silencio_partes'
    entries = state.setdefault('progresso', {})
    if folder.exists():
        entries[str(folder.resolve())] = {'assinatura': _assinar_local(pasta, _vinculo_progresso(state, folder, _arquivos_progresso(folder)))}
    else:
        entries.pop(str(folder.resolve()), None)
    _salvar(pasta, state)


def descartar_derivada_incompleta(pasta, origem, video):
    """Falha recuperável: descarta só a saída parcial e mantém as partes de retomada."""
    state, target = _destino_derivada(pasta, origem, video)
    target.unlink(missing_ok=True)
    if state.get('derivadas', {}).pop(str(target), None) is not None:
        _salvar(pasta, state)


def encerrar_operacao():
    _OPERACAO.set(None)


def _tempo(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return int(parsed.timestamp() * 1000)
    except (ValueError, AttributeError, TypeError, OverflowError):
        raise ErroLicenca('O prazo de autorização é inválido. Prepare uma nova autorização.') from None


def _assinar(pasta, action, ident, challenge, state, now):
    hashes, _, ec, utils = _crypto()
    body = {'autorizacao_id' if action == 'ativar' else 'sessao_id': ident, 'projeto': state['projeto'],
            'arquivo_sha256': state['arquivo_sha256'], 'desafio': challenge, 'nonce': secrets.token_urlsafe(24), 'emitido_em': now}
    message = _json(['iaedita-edicao-v1', action, ident, body['projeto'], body['arquivo_sha256'], challenge, body['nonce'], now]).encode('utf-8')
    signature = _chave(pasta).sign(message, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(signature)
    body['assinatura'] = _b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))
    return body


class _SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ErroLicenca('A conexão de autorização mudou de endereço. Preserve o projeto e contate o suporte IAEdita.')


def _post_json(action, body):
    if action not in ('ativar', 'renovar'):
        raise ErroLicenca('Operação de autorização inválida.')
    # A origem é fixa. Não aceitar URL do estado, argumento CLI ou variável de ambiente.
    request = urllib.request.Request(ORIGEM + '/api/edicao/' + action, data=_json(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'IAEdita/1.4.0'}, method='POST')
    client = urllib.request.build_opener(_SemRedirecionamento(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with client.open(request, timeout=15) as response:
            content = response.read(16385)
            if response.status != 200 or len(content) > 16384:
                raise ErroLicenca('A resposta de autorização não pôde ser confirmada. Preserve o projeto e tente mais tarde.')
            try:
                return json.loads(content)
            except ValueError:
                raise ErroLicenca('O serviço devolveu uma resposta de autorização inválida. Preserve o projeto e tente novamente mais tarde.',
                                  codigo='AUTORIZACAO_JSON_INVALIDO') from None
    except urllib.error.HTTPError as error:
        if 'x-deny-reason' in (error.headers or {}):  # sinal explícito do intermediário; o valor não é lido
            raise ErroLicenca(_REDE_RESTRITA, codigo='AUTORIZACAO_REDE_RESTRITA') from None
        if error.code == 403:
            mensagem = 'O servidor recusou a confirmação de autorização. Preserve o projeto para verificar a causa da recusa.'
        elif error.code in (400, 401, 409):
            mensagem = 'A edição não está autorizada. Confira o acesso na sua conta e prepare uma nova autorização para este projeto.'
        else:
            mensagem = 'O serviço de autorização está indisponível. Preserve o projeto e tente novamente mais tarde.'
        raise ErroLicenca(mensagem, codigo='AUTORIZACAO_HTTP', http_status=error.code) from None
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise _erro_comunicacao(error) from None


def _sondar_autorizacao():
    """GET de diagnóstico: None com HTTP 200, 'indisponivel' com 5xx ou tempo esgotado, 'bloqueio' no resto.
    Não envia dado do projeto e nunca levanta erro."""
    motivo = []

    def pedir():
        try:
            # O User-Agent padrão do Python recebe 403 da Cloudflare.
            request = urllib.request.Request(ORIGEM + '/healthz', headers={'User-Agent': 'IAEdita/1.4.0'})
            with urllib.request.build_opener(_SemRedirecionamento()).open(request, timeout=4) as response:
                motivo.append(None if response.status == 200 else 'bloqueio')
        except urllib.error.HTTPError as error:  # x-deny-reason: quem respondeu foi o intermediário, não o servidor
            motivo.append('indisponivel' if 500 <= error.code <= 599 and 'x-deny-reason' not in (error.headers or {}) else 'bloqueio')
        except Exception as error:
            motivo.append('indisponivel' if _erro_comunicacao(error).diagnostico['codigo'] == 'AUTORIZACAO_TIMEOUT' else 'bloqueio')

    pedido = threading.Thread(target=pedir, daemon=True)
    pedido.start()
    pedido.join(4)  # O timeout do urllib vale por leitura: resposta que goteja prenderia a chamada.
    return motivo[0] if motivo else 'indisponivel'


def autorizacao_alcancavel():
    """Só diagnóstico: true apenas com HTTP 200 do servidor."""
    return _sondar_autorizacao() is None


def situacao_da_autorizacao(internet):
    """(alcançável, motivo) para o comando ambiente. Sem internet em geral, nem 5xx nem demora provam servidor fora do ar."""
    motivo = _sondar_autorizacao()
    if motivo == 'indisponivel' and not internet:
        motivo = 'bloqueio'
    return motivo is None, motivo


def _validar_resposta(pasta, state, lease, now, action):
    try:
        expiry = _tempo(lease['expira_em'])
        expected = hashlib.sha256(_json(_publica(_chave(pasta))).encode('utf-8')).hexdigest()
        if (lease['projeto'] != state['projeto'] or lease['arquivo_sha256'] != state['arquivo_sha256']
                or lease['chave_sha256'] != expected or not isinstance(lease['usuario_id'], str) or not lease['usuario_id']
                or not isinstance(lease['sessao_id'], str) or len(lease['sessao_id']) != 43
                or not isinstance(lease['desafio'], str) or len(lease['desafio']) != 43
                or expiry <= now or expiry > now + _TTL + 60000):
            raise ValueError()
        old = state.get('sessao')
        if action == 'renovar' and old and (old['usuario_id'] != lease['usuario_id'] or old['sessao_id'] != lease['sessao_id']):
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise ErroLicenca('A resposta não corresponde à autorização deste projeto. Preserve o original e prepare uma nova autorização.') from None


def _executar(pasta, state, action, ident, challenge, now, transporte):
    pending = state.get('pendente')
    id_field = 'autorizacao_id' if action == 'ativar' else 'sessao_id'
    if pending and pending.get('acao') == action and pending.get('corpo', {}).get(id_field) == ident:
        body = pending['corpo']
        if abs(now - body.get('emitido_em', 0)) > 60000:
            raise ErroLicenca('A confirmação anterior venceu. Prepare uma nova autorização para retomar este projeto.',
                              codigo='AUTORIZACAO_CONFIRMACAO_EXPIRADA')
    else:
        body = _assinar(pasta, action, ident, challenge, state, now)
        state['pendente'] = {'acao': action, 'corpo': body}
        _salvar(pasta, state)  # Retentativa após resposta perdida usa exatamente a mesma prova.
    try:
        lease = (transporte or _post_json)(action, body)
    except ErroLicenca:
        raise
    except (OSError, http.client.HTTPException) as error:
        raise _erro_comunicacao(error) from None
    _validar_resposta(pasta, state, lease, now, action)
    state['sessao'] = lease
    state.pop('pendente', None)
    _salvar(pasta, state)
    return {'autorizado': True, 'expira_em': lease['expira_em']}


def ativar_autorizacao(pasta, autorizacao_id, desafio, expira_em, *, transporte=None, agora=None):
    now = int((agora or (lambda: time.time() * 1000))())
    if _tempo(expira_em) <= now:
        raise ErroLicenca('A autorização venceu. Prepare uma nova autorização deste projeto.', codigo='AUTORIZACAO_EXPIRADA')
    state = _estado(pasta)
    _conferir_original(pasta, state, state.get('original'))
    return _executar(pasta, state, 'ativar', autorizacao_id, desafio, now, transporte)


def exigir_autorizacao(pasta, video=None, *, transporte=None, agora=None):
    """Executado antes de cada comando protegido; nunca libera somente por estado local."""
    encerrar_operacao()
    now = int((agora or (lambda: time.time() * 1000))())
    state = _estado(pasta)
    _conferir_original(pasta, state, video)
    lease = state.get('sessao')
    if not isinstance(lease, dict) or not lease.get('sessao_id'):
        raise ErroLicenca('Autorize este projeto pela sua conta IAEdita antes de editar.')
    if _tempo(lease.get('expira_em')) <= now:
        raise ErroLicenca('A autorização de edição venceu. Prepare uma nova autorização para retomar este projeto.',
                          codigo='AUTORIZACAO_EXPIRADA')
    result = _executar(pasta, state, 'renovar', lease['sessao_id'], lease['desafio'], now, transporte)
    _OPERACAO.set((str(Path(pasta).resolve()), state['projeto'], state['arquivo_sha256'], _tempo(result['expira_em'])))
    return result

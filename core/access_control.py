import json
import logging
import re
import time
import unicodedata
from pathlib import Path


class AccessController:
    ROLE_ORDER = {
        "guest": 0,
        "user": 1,
        "admin": 2,
        "owner": 3,
    }

    def __init__(
        self,
        enabled: bool = False,
        owner_name: str = "owner",
        permission_ttl_seconds: int = 900,
        min_confidence: float = 0.75,
        camera_index: int = 0,
        auto_reload_gallery_seconds: int = 30,
        liveness_enabled: bool = True,
        liveness_min_movement_pixels: int = 4,
        identity_provider=None,
        registered_people_provider=None,
        time_provider=None,
        roles_file_path: str | None = None,
    ):
        self.enabled = bool(enabled)
        self.owner_name = self._normalize_name(owner_name)
        self.permission_ttl_seconds = max(30, int(permission_ttl_seconds))
        self.min_confidence = float(min_confidence)
        self.camera_index = int(camera_index)
        self.auto_reload_gallery_seconds = max(5, int(auto_reload_gallery_seconds))
        self.liveness_enabled = bool(liveness_enabled)
        self.liveness_min_movement_pixels = max(1, int(liveness_min_movement_pixels))
        self.identity_provider = identity_provider
        self.registered_people_provider = registered_people_provider
        self.time_provider = time_provider or time.time
        self.logger = logging.getLogger(__name__)
        self.roles_file_path = Path(roles_file_path) if roles_file_path else None

        self._permissions = {}
        self._roles = {}
        self._last_reload = 0.0
        self._recognizer = None
        self._cv2 = None
        self._load_roles()

    def authorize_command(self, command_text: str):
        if not self.enabled:
            return {"allowed": True, "handled": False, "user": None}

        identity = self._detect_identity()
        user = self._normalize_name(identity.get("name", ""))
        confidence = float(identity.get("confidence", 0.0))

        if not user or user == "unknown":
            return {
                "allowed": False,
                "handled": False,
                "user": None,
                "message": "Acesso negado: rosto nao reconhecido. Somente usuarios cadastrados podem usar comandos.",
            }

        if identity.get("liveness_ok") is False:
            return {
                "allowed": False,
                "handled": False,
                "user": user,
                "message": "Acesso negado: falha na prova de vida facial (anti-spoof).",
            }

        if confidence < self.min_confidence:
            return {
                "allowed": False,
                "handled": False,
                "user": user,
                "message": f"Acesso negado: confianca facial baixa ({confidence:.2f}).",
            }

        registered = self._registered_people()
        if user not in registered:
            return {
                "allowed": False,
                "handled": False,
                "user": user,
                "message": f"Acesso negado: usuario '{user}' nao cadastrado.",
            }

        management = self._parse_management_command(command_text)
        if management is not None:
            return self._handle_management_command(user, management, registered)

        if self._is_owner_only_command(command_text) and user != self.owner_name:
            return {
                "allowed": False,
                "handled": False,
                "user": user,
                "message": f"Apenas o dono ({self.owner_name}) pode cadastrar novos comandos de administrador.",
            }

        role = self._resolve_role(user)
        required_role = self._required_role_for_command(command_text)
        if self.ROLE_ORDER.get(role, 0) < self.ROLE_ORDER.get(required_role, 0):
            return {
                "allowed": False,
                "handled": False,
                "user": user,
                "role": role,
                "message": f"Acesso negado: comando exige papel '{required_role}', mas usuario esta como '{role}'.",
            }

        if role in {"owner", "admin"}:
            return {"allowed": True, "handled": False, "user": user, "role": role}

        if required_role == "guest":
            return {"allowed": True, "handled": False, "user": user, "role": role}

        if self._has_active_permission(user):
            return {"allowed": True, "handled": False, "user": user, "role": role}

        return {
            "allowed": False,
            "handled": False,
            "user": user,
            "role": role,
            "message": f"Acesso negado: '{user}' precisa de permissao do dono ({self.owner_name}).",
        }

    def _handle_management_command(self, requester, management, registered):
        action = management["action"]
        role = management.get("role")
        target = management.get("target")
        if requester != self.owner_name:
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                "message": f"Apenas o dono ({self.owner_name}) pode gerenciar permissoes.",
            }

        if action == "list":
            self._cleanup_expired_permissions()
            if not self._permissions:
                return {
                    "allowed": False,
                    "handled": True,
                    "user": requester,
                    "message": "Nenhuma permissao ativa no momento.",
                }

            now = self.time_provider()
            items = []
            for name, expiry in sorted(self._permissions.items()):
                seconds = max(0, int(expiry - now))
                items.append(f"{name}({seconds}s)")
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                    "message": "Permissoes ativas: " + ", ".join(items),
                }

        if action == "list_roles":
            roles = self.list_roles()
            details = ", ".join(f"{name}:{role_name}" for name, role_name in sorted(roles.items()))
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                "message": f"Papeis configurados: {details or 'nenhum'}",
            }

        if not target:
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                "message": "Informe um usuario para gerenciar permissao.",
            }

        target = self._normalize_name(target)
        if target not in registered:
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                "message": f"Usuario '{target}' nao esta cadastrado para acesso.",
            }

        if action == "set_role":
            normalized_role = self._normalize_role(role)
            if normalized_role is None:
                return {
                    "allowed": False,
                    "handled": True,
                    "user": requester,
                    "message": "Papel invalido. Use: guest, user, admin ou owner.",
                }
            if target == self.owner_name and normalized_role != "owner":
                return {
                    "allowed": False,
                    "handled": True,
                    "user": requester,
                    "message": "O dono principal nao pode ter papel rebaixado.",
                }
            self.set_role(target, normalized_role)
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                "message": f"Papel de '{target}' definido como '{normalized_role}'.",
            }

        if action == "grant":
            expiry = self.time_provider() + self.permission_ttl_seconds
            self._permissions[target] = expiry
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                "message": (
                    f"Permissao concedida para '{target}' por {self.permission_ttl_seconds}s."
                ),
            }

        if action == "revoke":
            self._permissions.pop(target, None)
            return {
                "allowed": False,
                "handled": True,
                "user": requester,
                "message": f"Permissao revogada para '{target}'.",
            }

        return {"allowed": False, "handled": True, "user": requester, "message": "Comando de permissao nao reconhecido."}

    def _has_active_permission(self, user):
        self._cleanup_expired_permissions()
        expiry = self._permissions.get(user)
        return bool(expiry and expiry > self.time_provider())

    def _cleanup_expired_permissions(self):
        now = self.time_provider()
        expired = [name for name, expiry in self._permissions.items() if expiry <= now]
        for name in expired:
            self._permissions.pop(name, None)

    def _parse_management_command(self, text):
        normalized = self._strip_accents(str(text or "").strip().lower())
        if not normalized:
            return None

        role_list_patterns = (
            r"^(listar|mostrar)\s+papeis\s*$",
            r"^(listar|mostrar)\s+roles\s*$",
        )
        for pattern in role_list_patterns:
            if re.match(pattern, normalized):
                return {"action": "list_roles"}

        role_set_patterns = (
            r"^(?:definir|atribuir|setar)\s+papel\s+(?:de\s+)?([a-z0-9_\-\s]+)\s+(?:como\s+)?(owner|admin|user|guest)\s*$",
            r"^(?:papel\s+de)\s+([a-z0-9_\-\s]+)\s+(?:=|como)\s*(owner|admin|user|guest)\s*$",
        )
        for pattern in role_set_patterns:
            match = re.match(pattern, normalized)
            if match:
                return {"action": "set_role", "target": match.group(1), "role": match.group(2)}

        if re.match(r"^(listar|mostrar)\s+(acessos|permissoes)\s*$", normalized):
            return {"action": "list"}

        for pattern in (
            r"^(autorizar|liberar|permitir)\s+(?:acesso\s+)?(?:para\s+)?([a-z0-9_\-\s]+)\s*$",
            r"^(dar permissao para)\s+([a-z0-9_\-\s]+)\s*$",
        ):
            match = re.match(pattern, normalized)
            if match:
                return {"action": "grant", "target": match.group(2 if len(match.groups()) > 1 else 1)}

        match = re.match(r"^(revogar|bloquear)\s+acesso\s+(?:de\s+)?([a-z0-9_\-\s]+)\s*$", normalized)
        if match:
            return {"action": "revoke", "target": match.group(2)}

        return None

    def _is_owner_only_command(self, text):
        normalized = self._strip_accents(str(text or "").strip().lower())
        if not normalized:
            return False

        return bool(
            re.match(
                r"^(?:(?:jarvis[\s,]+)?(?:adicionar|adiciona|cadastrar|registrar)\s+(?:o\s+)?comando(?:s)?\b|(?:iniciar|abrir|comecar)\s+assistente\s+de\s+dispositivo\b|definir\s+acao\s+(?:abrir|fechar)\b|(?:finalizar|concluir|cancelar|encerrar)\s+assistente\s+de\s+dispositivo\b)",
                normalized,
            )
        )

    def list_roles(self):
        roles = {self.owner_name: "owner"}
        for name, role in self._roles.items():
            normalized_name = self._normalize_name(name)
            normalized_role = self._normalize_role(role)
            if normalized_name and normalized_role:
                roles[normalized_name] = normalized_role
        return roles

    def set_role(self, user_name: str, role: str):
        user = self._normalize_name(user_name)
        normalized_role = self._normalize_role(role)
        if not user or normalized_role is None:
            return False
        self._roles[user] = normalized_role
        self._save_roles()
        return True

    def _resolve_role(self, user):
        normalized_user = self._normalize_name(user)
        if normalized_user == self.owner_name:
            return "owner"
        mapped = self._normalize_role(self._roles.get(normalized_user, "user"))
        return mapped or "user"

    def _required_role_for_command(self, command_text):
        normalized = self._strip_accents(str(command_text or "").strip().lower())
        if not normalized:
            return "guest"

        if normalized in {"sair", "exit", "quit", "ajuda", "help", "?", "status", "memoria"}:
            return "guest"

        owner_only_patterns = (
            r"^(?:autorizar|liberar|permitir)\s+(?:acesso\s+)?(?:para\s+)?",
            r"^(?:dar permissao para)\b",
            r"^(?:revogar|bloquear)\s+acesso\s+(?:de\s+)?",
            r"^(?:definir|atribuir|setar)\s+papel\b",
            r"^(?:papel\s+de)\b",
            r"^(?:listar|mostrar)\s+papeis\b",
        )
        for pattern in owner_only_patterns:
            if re.match(pattern, normalized):
                return "owner"
        if self._is_owner_only_command(normalized):
            return "owner"

        admin_patterns = (
            r"^(?:bloquear|desbloquear)\s+internet\b",
            r"^(?:bloquear|desbloquear)\s+maquina\b",
            r"^(?:registrar|cadastrar)\s+maquina\b",
            r"^(?:listar)\s+bloqueios\s+de\s+rede\b",
            r"^(?:iniciar|parar|status|resumo)\s+(?:rastreamento|monitoramento)\s+de\s+rede\b",
            r"^(?:exportar|importar)\s+memoria\b",
            r"^(?:criar|executar|rodar|ativar|listar|remover|apagar|deletar)\s+cena\b",
            r"^(?:agendar)\s+cena\b",
            r"^(?:listar)\s+agendamentos\b",
            r"^(?:cancelar|remover|deletar)\s+agendamento\b",
            r"^(?:criar|listar|remover|apagar|deletar)\s+regra\b",
            r"^(?:disparar)\s+evento\b",
            r"^(?:executar|rodar|fazer)\s+backup\b",
            r"^(?:status)\s+(?:do\s+)?backup\b",
            r"^(?:executar|rodar|fazer)\s+testes\b",
            r"^(?:status)\s+(?:dos\s+)?testes\b",
            r"^(?:iniciar|ativar|ligar|comecar|parar|desativar|desligar|status|resumo)\s+(?:monitoramento\s+de\s+sistema|(?:recursos|cpu|ram)\s+do\s+sistema)\b",
            r"^(?:status)\s+(?:da\s+)?manutencao\b",
            r"^(?:executar|rodar|fazer)\s+manutencao\b",
            r"^(?:listar|recarregar|atualizar)\s+plugins\b",
        )
        for pattern in admin_patterns:
            if re.match(pattern, normalized):
                return "admin"

        return "user"

    def _load_roles(self):
        self._roles = {}
        if self.roles_file_path is None:
            self._roles[self.owner_name] = "owner"
            return

        if not self.roles_file_path.exists():
            self._roles[self.owner_name] = "owner"
            return
        try:
            with self.roles_file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle) or {}
            roles = payload.get("roles", {}) if isinstance(payload, dict) else {}
            if isinstance(roles, dict):
                for raw_name, raw_role in roles.items():
                    normalized_name = self._normalize_name(raw_name)
                    normalized_role = self._normalize_role(raw_role)
                    if normalized_name and normalized_role:
                        self._roles[normalized_name] = normalized_role
        except Exception:
            self._roles = {}

        self._roles[self.owner_name] = "owner"
        self._save_roles()

    def _save_roles(self):
        if self.roles_file_path is None:
            return
        self.roles_file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"roles": self.list_roles()}
        with self.roles_file_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_role(role):
        value = str(role or "").strip().lower()
        if value in AccessController.ROLE_ORDER:
            return value
        return None

    def _registered_people(self):
        if callable(self.registered_people_provider):
            people = self.registered_people_provider() or []
            return {self._normalize_name(name) for name in people if self._normalize_name(name)}

        recognizer = self._get_recognizer()
        if recognizer is None:
            return {self.owner_name} if self.owner_name else set()

        try:
            if hasattr(recognizer, "reload_gallery"):
                now = self.time_provider()
                if now - self._last_reload > self.auto_reload_gallery_seconds:
                    recognizer.reload_gallery()
                    self._last_reload = now
            if hasattr(recognizer, "list_known_people"):
                people = recognizer.list_known_people()
                return {self._normalize_name(name) for name in people if self._normalize_name(name)}
            embeddings = getattr(recognizer, "known_embeddings", {})
            return {self._normalize_name(name) for name in embeddings.keys() if self._normalize_name(name)}
        except Exception as exc:
            self.logger.warning("Falha ao carregar cadastrados faciais: %s", exc)
            return {self.owner_name} if self.owner_name else set()

    def _detect_identity(self):
        if callable(self.identity_provider):
            value = self.identity_provider() or {}
            return {
                "name": value.get("name"),
                "confidence": float(value.get("confidence", 0.0)),
                "liveness_ok": bool(value.get("liveness_ok", True)),
            }

        cv2 = self._get_cv2()
        recognizer = self._get_recognizer()
        if cv2 is None or recognizer is None:
            return {"name": None, "confidence": 0.0, "liveness_ok": False}

        capture = cv2.VideoCapture(self.camera_index)
        if not capture or not capture.isOpened():
            return {"name": None, "confidence": 0.0, "liveness_ok": False}

        best_name = None
        best_confidence = 0.0
        best_centers = []
        try:
            for _ in range(3):
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                faces = recognizer.detect_faces(frame) or []
                for face in faces:
                    name = self._normalize_name(face.get("name"))
                    confidence = float(face.get("confidence", 0.0))
                    if not name or name == "unknown":
                        continue
                    bbox = face.get("bbox") or (0, 0, 0, 0)
                    center = self._bbox_center(bbox)
                    if confidence > best_confidence:
                        best_name = name
                        best_confidence = confidence
                        best_centers = [center]
                    elif name == best_name:
                        best_centers.append(center)
        except Exception as exc:
            self.logger.warning("Falha ao identificar usuario pela camera: %s", exc)
            return {"name": None, "confidence": 0.0, "liveness_ok": False}
        finally:
            try:
                capture.release()
            except Exception:
                pass

        liveness_ok = True
        if self.liveness_enabled:
            liveness_ok = self._check_liveness(best_centers)

        return {"name": best_name, "confidence": best_confidence, "liveness_ok": liveness_ok}

    def _check_liveness(self, centers):
        if not centers or len(centers) < 2:
            return False

        first_x, first_y = centers[0]
        for cx, cy in centers[1:]:
            if abs(cx - first_x) >= self.liveness_min_movement_pixels:
                return True
            if abs(cy - first_y) >= self.liveness_min_movement_pixels:
                return True
        return False

    @staticmethod
    def _bbox_center(bbox):
        if not bbox or len(bbox) != 4:
            return (0, 0)
        x1, y1, x2, y2 = bbox
        return (int((x1 + x2) / 2), int((y1 + y2) / 2))

    def _get_recognizer(self):
        if self._recognizer is not None:
            return self._recognizer
        try:
            from core.face_gallery import FaceRecognizer

            self._recognizer = FaceRecognizer()
        except Exception as exc:
            self.logger.warning("Reconhecimento facial indisponivel para controle de acesso: %s", exc)
            self._recognizer = None
        return self._recognizer

    def _get_cv2(self):
        if self._cv2 is not None:
            return self._cv2
        try:
            import cv2

            self._cv2 = cv2
        except Exception:
            self._cv2 = None
        return self._cv2

    @staticmethod
    def _normalize_name(name):
        value = AccessController._strip_accents(str(name or "").strip().lower())
        value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
        return value.strip("_")

    @staticmethod
    def _strip_accents(value):
        normalized = unicodedata.normalize("NFKD", value)
        return "".join(char for char in normalized if not unicodedata.combining(char))

import unittest

from core.access_control import AccessController


class AccessControlTests(unittest.TestCase):
    def test_disabled_mode_allows_commands(self):
        controller = AccessController(enabled=False)

        result = controller.authorize_command("ligar luz")

        self.assertTrue(result["allowed"])
        self.assertFalse(result["handled"])

    def test_denies_unknown_face(self):
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            identity_provider=lambda: {"name": "unknown", "confidence": 0.99},
            registered_people_provider=lambda: ["dono", "maria"],
        )

        result = controller.authorize_command("ligar luz")

        self.assertFalse(result["allowed"])
        self.assertIn("rosto nao reconhecido", result["message"].lower())

    def test_denies_unregistered_user(self):
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            identity_provider=lambda: {"name": "invasor", "confidence": 0.99},
            registered_people_provider=lambda: ["dono", "maria"],
        )

        result = controller.authorize_command("ligar luz")

        self.assertFalse(result["allowed"])
        self.assertIn("nao cadastrado", result["message"].lower())

    def test_owner_grants_temporary_permission_and_user_expires(self):
        now = [1000.0]
        identity = {"name": "dono", "confidence": 0.99}

        controller = AccessController(
            enabled=True,
            owner_name="dono",
            permission_ttl_seconds=60,
            identity_provider=lambda: identity,
            registered_people_provider=lambda: ["dono", "maria"],
            time_provider=lambda: now[0],
        )

        granted = controller.authorize_command("autorizar acesso para maria")
        self.assertTrue(granted["handled"])
        self.assertIn("concedida", granted["message"].lower())

        identity.update({"name": "maria", "confidence": 0.99})
        allowed = controller.authorize_command("ligar luz")
        self.assertTrue(allowed["allowed"])

        now[0] += 61.0
        denied = controller.authorize_command("ligar luz")
        self.assertFalse(denied["allowed"])
        self.assertIn("precisa de permissao", denied["message"].lower())

    def test_non_owner_cannot_manage_permissions(self):
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            identity_provider=lambda: {"name": "maria", "confidence": 0.99},
            registered_people_provider=lambda: ["dono", "maria"],
        )

        result = controller.authorize_command("autorizar acesso para maria")

        self.assertTrue(result["handled"])
        self.assertFalse(result["allowed"])
        self.assertIn("apenas o dono", result["message"].lower())

    def test_owner_can_revoke_permission(self):
        identity = {"name": "dono", "confidence": 0.99}
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            permission_ttl_seconds=300,
            identity_provider=lambda: identity,
            registered_people_provider=lambda: ["dono", "maria"],
        )

        controller.authorize_command("autorizar maria")
        revoked = controller.authorize_command("revogar acesso de maria")
        self.assertTrue(revoked["handled"])
        self.assertIn("revogada", revoked["message"].lower())

        identity.update({"name": "maria", "confidence": 0.99})
        denied = controller.authorize_command("ligar luz")
        self.assertFalse(denied["allowed"])

    def test_owner_management_accepts_accents_and_spaces(self):
        identity = {"name": "dono", "confidence": 0.99}
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            permission_ttl_seconds=300,
            identity_provider=lambda: identity,
            registered_people_provider=lambda: ["dono", "joao_silva"],
        )

        granted = controller.authorize_command("dar permiss\u00e3o para Jo\u00e3o Silva")
        self.assertTrue(granted["handled"])
        self.assertIn("concedida", granted["message"].lower())

        identity.update({"name": "jo\u00e3o silva", "confidence": 0.99})
        allowed = controller.authorize_command("abrir portao")
        self.assertTrue(allowed["allowed"])

    def test_non_owner_cannot_register_admin_device_commands_even_with_permission(self):
        now = [1000.0]
        identity = {"name": "dono", "confidence": 0.99}
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            permission_ttl_seconds=300,
            identity_provider=lambda: identity,
            registered_people_provider=lambda: ["dono", "maria"],
            time_provider=lambda: now[0],
        )

        controller.authorize_command("autorizar maria")
        identity.update({"name": "maria", "confidence": 0.99})
        denied = controller.authorize_command("adicionar comando para dispositivo janela para abrir e fechar")

        self.assertFalse(denied["allowed"])
        self.assertIn("apenas o dono", denied["message"].lower())

    def test_owner_can_set_role_and_list_roles(self):
        identity = {"name": "dono", "confidence": 0.99}
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            identity_provider=lambda: identity,
            registered_people_provider=lambda: ["dono", "maria"],
        )

        set_role = controller.authorize_command("definir papel maria admin")
        list_roles = controller.authorize_command("listar papeis")

        self.assertTrue(set_role["handled"])
        self.assertIn("definido como 'admin'", set_role["message"].lower())
        self.assertTrue(list_roles["handled"])
        self.assertIn("maria:admin", list_roles["message"].lower())

    def test_admin_can_execute_critical_without_temporary_permission(self):
        identity = {"name": "dono", "confidence": 0.99}
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            identity_provider=lambda: identity,
            registered_people_provider=lambda: ["dono", "maria"],
        )
        controller.authorize_command("definir papel maria admin")

        identity.update({"name": "maria", "confidence": 0.99})
        allowed = controller.authorize_command("bloquear internet")

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed.get("role"), "admin")

    def test_maintenance_commands_require_admin_role(self):
        identity = {"name": "dono", "confidence": 0.99}
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            identity_provider=lambda: identity,
            registered_people_provider=lambda: ["dono", "maria"],
        )

        identity.update({"name": "maria", "confidence": 0.99})
        denied = controller.authorize_command("status manutencao")
        self.assertFalse(denied["allowed"])
        self.assertIn("exige papel 'admin'", denied["message"].lower())

        identity.update({"name": "dono", "confidence": 0.99})
        controller.authorize_command("definir papel maria admin")
        identity.update({"name": "maria", "confidence": 0.99})
        allowed = controller.authorize_command("executar manutencao agora")

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed.get("role"), "admin")

    def test_liveness_failure_blocks_access(self):
        controller = AccessController(
            enabled=True,
            owner_name="dono",
            identity_provider=lambda: {"name": "dono", "confidence": 0.99, "liveness_ok": False},
            registered_people_provider=lambda: ["dono"],
        )

        denied = controller.authorize_command("status")
        self.assertFalse(denied["allowed"])
        self.assertIn("prova de vida", denied["message"].lower())


if __name__ == "__main__":
    unittest.main()

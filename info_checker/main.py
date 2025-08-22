import argparse
import json
import os
import sys
from typing import List

import yaml
from info_checker.core.models import Task, CollectRequest, ValidationRule
from info_checker.core.runner import Runner


def load_tasks(cfg: dict) -> List[Task]:
    """
    Constrói a lista de Tasks a partir do YAML.
    Agora 'extraction' e 'rules' são OPCIONAIS:
      - Se não existirem, usamos extraction={"strategy":"none","pattern":""} e rules=[]
      - Isso permite tarefas cujo foco é exportação/automação via Playwright, sem regex/validação.
    """
    if cfg is None:
        raise ValueError("Arquivo YAML vazio ou inválido (yaml.safe_load retornou None).")

    if "tasks" not in cfg:
        raise KeyError("A chave obrigatória 'tasks' não foi encontrada no config.yaml.")

    if not isinstance(cfg["tasks"], list):
        raise TypeError("A chave 'tasks' deve ser uma lista de tarefas.")

    tasks: List[Task] = []

    for idx, t in enumerate(cfg["tasks"], start=1):
        if not isinstance(t, dict):
            raise TypeError(f"Tarefa #{idx} não é um objeto YAML (dict).")

        # Agora só exigimos chaves essenciais:
        for req_key in ("id", "collector", "request"):
            if req_key not in t:
                raise KeyError(f"Tarefa '{t.get('id', f'#{idx}')}' sem a chave obrigatória: {req_key}")

        # Construção do CollectRequest
        req = CollectRequest(**t["request"])

        # extraction/rules tornam-se opcionais
        extraction = t.get("extraction")
        rules_raw = t.get("rules")

        # Defaults amigáveis quando não vier nada
        if extraction is None:
            extraction = {"strategy": "none", "pattern": ""}

        rules: List[ValidationRule] = []
        if isinstance(rules_raw, list):
            rules = [ValidationRule(**r) for r in rules_raw]
        elif rules_raw is None:
            rules = []
        else:
            raise TypeError(f"Tarefa '{t['id']}': 'rules' deve ser lista quando presente.")

        # Log leve para ajudar o usuário a entender que validação foi pulada
        if extraction.get("strategy") == "none" and not rules:
            print(f"[INFO] Tarefa '{t['id']}' sem 'extraction/rules' — validação será pulada.", file=sys.stderr)

        tasks.append(
            Task(
                id=t["id"],
                collector=t["collector"],
                request=req,
                extraction=extraction,
                rules=rules,
            )
        )

    return tasks


def parse_args():
    ap = argparse.ArgumentParser(description="Info Checker Runner")
    default_cfg = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    ap.add_argument(
        "--config",
        "-c",
        default=default_cfg,
        help=f"Caminho para o arquivo config.yaml (default: {default_cfg})",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    cfg_path = os.path.abspath(args.config)

    if not os.path.exists(cfg_path):
        print(f"[ERRO] config.yaml não encontrado em: {cfg_path}", file=sys.stderr)
        return 2

    print(f"[INFO] Usando config: {cfg_path}")

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print("[ERRO] Falha ao parsear YAML do config:", e, file=sys.stderr)
        return 2

    # debug opcional
    try:
        print("[DEBUG] Config keys:", list(cfg.keys()) if isinstance(cfg, dict) else type(cfg).__name__)
    except Exception:
        pass

    try:
        runner = Runner(cfg_collectors=cfg.get("collectors", {}) if isinstance(cfg, dict) else {})
        tasks = load_tasks(cfg)
    except Exception as e:
        print(f"[ERRO] Config inválido: {e}", file=sys.stderr)
        return 2

    # executa cada task
    exit_code = 0
    for task in tasks:
        try:
            result = runner.run_task(task)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if not result.get("ok"):
                exit_code = 1
        except Exception as e:
            print(f"[ERRO] Falha ao executar a task '{task.id}': {e}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

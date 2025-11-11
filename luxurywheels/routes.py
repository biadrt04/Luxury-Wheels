# Criar as rotas do nosso site
from flask import render_template, url_for, redirect, flash, request, jsonify
from luxurywheels import app, db, bcrypt
from luxurywheels.models import Usuario, Veiculo, Aluguel
from flask_login import login_required, login_user, logout_user, current_user
from luxurywheels.forms import FormLogin, FormRegistro
from datetime import datetime, date
import math


@app.route("/", methods=["GET", "POST"])
def login():
    formLogin = FormLogin()
    if formLogin.validate_on_submit():
        usuario = Usuario.query.filter_by(email=formLogin.email.data).first()
        if usuario is None:
            flash('* Nenhum usuário encontrado com este e-mail.', 'danger')
        elif not bcrypt.check_password_hash(usuario.senha, formLogin.senha.data):
            flash('* Senha incorreta.', 'danger')
        else:
            login_user(usuario)
            return redirect(url_for("veiculos", id_usuario=usuario.id))
    return render_template("login.html", form=formLogin)

@app.route("/registro", methods=["GET", "POST"])
def registro():
    formRegistro = FormRegistro()
    if formRegistro.validate_on_submit():
        usuario_existente = Usuario.query.filter(
            (Usuario.email == formRegistro.email.data) |
            (Usuario.username == formRegistro.username.data)
        ).first()

        if usuario_existente:
            flash('* Usuário ou e-mail já existente. Faça login.', 'danger')
            return redirect(url_for("login"))

        senha = bcrypt.generate_password_hash(formRegistro.senha.data)
        usuario = Usuario(
            username=formRegistro.username.data,
            senha=senha,
            email=formRegistro.email.data,
            telefone=formRegistro.telefone.data
        )

        db.session.add(usuario)
        db.session.commit()
        login_user(usuario, remember=True)
        return redirect(url_for("escolher_categoria", id_usuario=usuario.id))
    return render_template("registro.html", form=formRegistro)

@app.route("/escolher_categoria/<int:id_usuario>", methods=["GET", "POST"])
def escolher_categoria(id_usuario):
    usuario = Usuario.query.get(int(id_usuario))

    if request.method == "POST":
        categoria = request.form["categoria"].lower()
        usuario.categoria = categoria
        db.session.commit()
        return redirect(url_for("veiculos", id_usuario=usuario.id))

    return render_template("escolher_categoria.html", usuario=usuario)

@app.route("/painel/<int:id_usuario>")
@login_required
def painel(id_usuario):
    usuario = Usuario.query.get(int(id_usuario))
    db.session.refresh(usuario)
    return render_template("painel.html", usuario=usuario)

@app.route("/editar_perfil/<int:id_usuario>", methods=["GET", "POST"])
@login_required
def editar_perfil(id_usuario):
    usuario = Usuario.query.get(id_usuario)

    # garante que o usuário só edite o próprio perfil
    if usuario.id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for("painel", id_usuario=current_user.id))

    if request.method == "POST":
        usuario.username = request.form["username"]
        usuario.email = request.form["email"]
        usuario.telefone = request.form["telefone"]
        usuario.categoria = request.form["categoria"].lower()

        db.session.commit()
        login_user(usuario)
        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("painel", id_usuario=usuario.id))

    return render_template("editar_perfil.html", usuario=usuario)

@app.route("/veiculos/<id_usuario>", methods=["GET", "POST"])
@login_required
def veiculos(id_usuario):
    usuario = Usuario.query.get(int(id_usuario))

    # Marca, modelo e lugares selecionados
    marca_selecionada = request.args.get("marca")
    modelo_selecionado = request.args.get("modelo")
    lugares_selecionado = request.args.get("lugares")

    # Todas as marcas (únicas)
    marcas = [m[0] for m in db.session.query(Veiculo.marca).distinct().all()]


    # Se o usuário escolheu uma marca, mostra só os modelos dessa marca.
    if marca_selecionada:
        modelos = [
            m[0]
            for m in db.session.query(Veiculo.modelo)
            .filter(Veiculo.marca == marca_selecionada)
            .distinct()
            .all()
        ]
    else:
        modelos = [m[0] for m in db.session.query(Veiculo.modelo).distinct().all()]

    # Agora aplica os filtros aos veículos
    query = Veiculo.query
    if marca_selecionada:
        query = query.filter(Veiculo.marca == marca_selecionada)
    if modelo_selecionado:
        query = query.filter(Veiculo.modelo == modelo_selecionado)
    if lugares_selecionado:
        query = query.filter(Veiculo.quantidade_lugares == lugares_selecionado)

    preco_max = request.args.get("preco", type=float)
    preco_min = request.args.get("precomin", type=float)
    if preco_max:
        query = query.filter(Veiculo.preco_diaria <= preco_max)
    if preco_min:
        query = query.filter(Veiculo.preco_diaria >= preco_min)

    carros = query.all()
    hoje = date.today()
    veiculos_todos = Veiculo.query.all()

    for v in veiculos_todos:
        indisponivel = False

        # Verifica se há aluguel ativo
        aluguel_ativo = (
            Aluguel.query
            .filter_by(veiculo_id=v.id)
            .filter(Aluguel.status != "Cancelada")
            # Filtra por aluguéis onde hoje está entre data_inicio e data_fim (inclusive)
            .filter(Aluguel.data_fim >= hoje)
            .first()
        )
        if aluguel_ativo:
            indisponivel = True

        # Se a inspeção mais recente foi há mais de 365 dias, fica indisponível.
        elif v.data_ultima_inspecao and (hoje - v.data_ultima_inspecao).days > 365:
            indisponivel = True
            print(v.modelo, "→ inspeção vencida")

        # Se a data da próxima revisão já passou, fica indisponível.
        elif v.data_proxima_revisao and v.data_proxima_revisao < hoje:
            indisponivel = True
            print(v.modelo, "→ revisão vencida")

        # Se indisponivel for True, novo_valor será False (indisponível)
        # Se indisponivel for False, novo_valor será True (disponível)
        novo_valor = not indisponivel

        # Só faz o update se o valor mudou para evitar commits desnecessários
        if v.disponivel != novo_valor:
            v.disponivel = novo_valor

    # Commit único para todas as alterações de disponibilidade dos veículos
    db.session.commit()

    # Verifica o valor dos carros para aplicar a categoria de cada um
    for carro in veiculos_todos:
        if not carro.categoria or carro.categoria.strip() == "":
            if carro.preco_diaria <= 100:
                carro.categoria = "Econômico"
            elif carro.preco_diaria <= 150:
                carro.categoria = "Silver"
            else:
                carro.categoria = "Gold"

    db.session.commit()

    # Função para verificar a escolha de categoria do usuário
    def tem_acesso(usuario, veiculo):
        if usuario.categoria.lower() == "gold":
            return True
        elif usuario.categoria.lower() == "silver" and veiculo.categoria.lower() in ["silver", "econômico"]:
            return True
        elif usuario.categoria.lower() == "econômico" and veiculo.categoria.lower() == "econômico":
            return True
        return False

    CARDS_POR_PAGINA = 4
    total_carros = len(carros)

    if total_carros > 0:
        total_paginas = math.ceil(total_carros / CARDS_POR_PAGINA)
    else:
        total_paginas = 0

    return render_template(
        "veiculos.html",
        usuario=usuario,
        carros=carros,
        marcas=marcas,
        modelos=modelos,
        marca_selecionada=marca_selecionada,
        modelo_selecionado=modelo_selecionado,
        total_paginas=total_paginas,
        tem_acesso=tem_acesso
    )


@app.route("/alugar/<int:carro_id>/<int:usuario_id>", methods=['GET', 'POST'])
def alugar(carro_id, usuario_id):
    usuario = Usuario.query.get(int(usuario_id))
    carro = Veiculo.query.get(int(carro_id))

    if request.method =='POST':
        data_inicio = request.form.get("inicio")
        data_fim = request.form.get("fim")
        nome = request.form.get("nome")
        telefone = request.form.get("telefone")
        email = request.form.get("email")
        cpf = request.form.get("cpf")
        cep = request.form.get("cep")

        inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
        forma_pagamento = request.form.get("forma_pagamento")


        dias = (fim - inicio).days
        if dias == 0:
            dias = 1
        valor_total = dias * carro.preco_diaria

        aluguel = Aluguel(
            usuario_id=usuario.id,
            veiculo_id=carro.id,
            data_inicio=inicio,
            data_fim=fim,
            valor_total=valor_total,
            status="Pendente",
            forma_pagamento=forma_pagamento,
            status_pagamento="Pendente",
            nome = nome,
            telefone = telefone,
            email = email,
            cpf = cpf,
            cep = cep
        )

        db.session.add(aluguel)
        carro.disponivel = False
        db.session.commit()
        return redirect(url_for("reservas", usuario_id=usuario.id))

    return render_template("alugar.html", usuario=usuario, carro=carro)

@app.route("/reservas/<int:usuario_id>")
def reservas(usuario_id):
    usuario = Usuario.query.get(int(usuario_id))
    reservas = Aluguel.query.filter_by(usuario_id=usuario_id).filter(Aluguel.status != "Cancelada").all()
    return render_template("reservas.html", usuario=usuario, reservas=reservas)

@app.route("/cancelar_reserva/<int:reserva_id>/<int:usuario_id>", methods=["POST"])
def cancelar_reserva(reserva_id, usuario_id):
    reserva = Aluguel.query.get(reserva_id)
    if reserva:
        reserva.status = "Cancelada"
        reserva.veiculo.disponivel = True
        db.session.commit()
        flash("* Reserva cancelada com sucesso!", f"success-{reserva.id}")
    else:
        flash("* Reserva não encontrada.", f"danger-{reserva_id}")
    return redirect(url_for("reservas", usuario_id=usuario_id))

@app.route("/alterar_reserva/<int:reserva_id>/<int:usuario_id>", methods=["GET","POST"])
def alterar_reserva(reserva_id, usuario_id):
    reserva = Aluguel.query.get(reserva_id)
    usuario = reserva.usuario
    carro = reserva.veiculo

    if request.method == "GET":
        return render_template("alugar.html",
                               usuario=usuario,
                               carro=carro,
                               reserva=reserva)

    nova_data_inicio = request.form.get("inicio")
    nova_data_fim = request.form.get("fim")
    nome = request.form.get("nome")
    telefone = request.form.get("telefone")
    email = request.form.get("email")
    cpf = request.form.get("cpf")
    cep = request.form.get("cep")
    forma_pagamento = request.form.get("forma_pagamento")

    reserva.nome = nome
    reserva.telefone = telefone
    reserva.email = email
    reserva.cpf = cpf
    reserva.cep = cep
    reserva.forma_pagamento = forma_pagamento

    if nova_data_inicio and nova_data_fim:
        reserva.data_inicio = datetime.strptime(nova_data_inicio, "%Y-%m-%d").date()
        reserva.data_fim = datetime.strptime(nova_data_fim, "%Y-%m-%d").date()

        # recalcular valor_total, igual em alugar
        dias = (reserva.data_fim - reserva.data_inicio).days
        if dias == 0:
            dias = 1
        reserva.valor_total = dias * reserva.veiculo.preco_diaria

    reserva.status = "Alterada"

    db.session.commit()
    flash("* Reserva alterada com sucesso!", f"danger-{reserva.id}")
    return redirect(url_for("reservas", usuario_id=usuario_id, reserva_id=reserva.id))


@app.route("/api/modelos/<marca>", methods=["GET"])
def get_modelos_por_marca(marca):

    # Busca os modelos no banco de dados
    modelos = [
        m[0]
        for m in db.session.query(Veiculo.modelo)
        .filter(Veiculo.marca == marca)
        .distinct()
        .all()
    ]
    return jsonify(modelos)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# Criar a estrutura do banco de dados
# (database.Model)Transforma sua classe Python em uma tabela do banco de dados,
# e te dá métodos prontos para manipular os dados.

from luxurywheels import db, login_manager
from flask_login import UserMixin
from datetime import date, timedelta

@login_manager.user_loader
def load_usuario(id_usuario):
    return Usuario.query.get(int(id_usuario))


class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(100), unique=False, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False, default="")
    categoria = db.Column(db.String(20), default="Econômico")

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    preco_diaria = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.Text)
    foto = db.Column(db.String(200))
    disponivel = db.Column(db.Boolean, default=True)
    data_ultima_revisao = db.Column(db.Date)
    data_proxima_revisao = db.Column(db.Date)
    data_ultima_inspecao = db.Column(db.Date)
    quantidade_lugares = db.Column(db.Integer)
    categoria = db.Column(db.String(20), default="Econômico")

    def status(self):
        hoje = date.today()
        um_ano = timedelta(days=365)

        # Verifica manutenção primeiro
        if self.data_ultima_inspecao and (hoje - self.data_ultima_inspecao) > um_ano:
            return "manutencao"

        if self.data_proxima_revisao and self.data_proxima_revisao < hoje:
            return "manutencao"

        # Depois verifica se está alugado
        if not self.disponivel:
            return "alugado"

        # Caso contrário, está disponível
        return "disponivel"


class Aluguel(db.Model):
    __tablename__ = "aluguel"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Pendente")
    forma_pagamento = db.Column(db.String(50))
    status_pagamento = db.Column(db.String(50), default="Pendente")
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(15), nullable=False)
    cep = db.Column(db.String(20), nullable=False)
    usuario = db.relationship('Usuario', backref='alugueis')
    veiculo = db.relationship('Veiculo', backref='alugueis')



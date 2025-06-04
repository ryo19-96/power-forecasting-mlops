variable "region" {
  type = string
}

# アベイラビリティゾーン（同じリージョン内にある物理的に分離されたデータセンター群）
variable "azs" {
  type = list(string)
}

variable "vpc_cidr" {
  type = string
}

# NAT Gatewayを有効にするかどうか
variable "enable_nat_gateway" {
  type    = bool
  default = false # デフォルトは無効
}

# aws VPC
resource "aws_vpc" "vpc" {
  cidr_block           = var.vpc_cidr # IP範囲
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {
    Name = "power-forecast-vpc-${terraform.workspace}"
  }
}

# Public と Private それぞれ必要

# === Publicサブネット + ルート ===
# Publicサブネットは、インターネットゲートウェイを通じてインターネットにアクセス可能（NAT Gateway配置、Web UI公開）

# インターネットゲートウェイ
resource "aws_internet_gateway" "internet_gateway" {
  vpc_id = aws_vpc.vpc.id
  tags = {
    Name = "power-forecast-internet-gateway-${terraform.workspace}"
  }
}

resource "aws_subnet" "public_subnet" {
  count             = length(var.azs) # アベイラビリティゾーンの数だけサブネットを作成（ループさせる）
  vpc_id            = aws_vpc.vpc.id
  availability_zone = element(var.azs, count.index)
  # cidrsubnet(親CIDR, 分割ビット数, 番号)
  # 8=分割するビット数、11=Publicサブネットの開始番号（=11以降の/24を使用する）
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 11) # 10.0.11.0/24, 10.0.12.0/24
  map_public_ip_on_launch = true                                          # EC2に自動でパブリックIP付与
  tags = {
    Name = "power-forecast-public-${count.index}"
  }
}

resource "aws_route_table" "public_route_table" {
  vpc_id = aws_vpc.vpc.id

  route {
    cidr_block = "0.0.0.0/0" # 全通信
    gateway_id = aws_internet_gateway.internet_gateway.id
  }
  tags = {
    Name = "power-forecast-public-route-${terraform.workspace}"
  }
}

resource "aws_route_table_association" "public_route_table_associations" {
  count          = length(aws_subnet.public_subnet)
  subnet_id      = aws_subnet.public_subnet[count.index].id
  route_table_id = aws_route_table.public_route_table.id
}

# === Privateサブネット + ルート ===
# Privateサブネットは、NAT Gatewayを通じてインターネットにアクセス可能（MWAAのScheduler / Worker配置）

# NAT Gateway（1 AZ に1つ）
resource "aws_eip" "nat_gateway_elastic_ips" {
  count      = var.enable_nat_gateway ? length(var.azs) : 0 # NAT Gatewayを有効にする場合のみ作成
  depends_on = [aws_internet_gateway.internet_gateway]
}

resource "aws_nat_gateway" "nat_gateways" {
  count         = var.enable_nat_gateway ? length(var.azs) : 0 # NAT Gatewayを有効にする場合のみ作成
  allocation_id = aws_eip.nat_gateway_elastic_ips[count.index].id
  subnet_id     = aws_subnet.public_subnet[count.index].id # Publicサブネットに配置
  tags = {
    Name = "power-forecast-nat-gateways-${count.index}"
  }
}

# Privateサブネット + ルート
resource "aws_subnet" "private_subnet" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.vpc.id
  availability_zone = element(var.azs, count.index)
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 21) # 10.0.21.0/24, 10.0.22.0/24
  tags = {
    Name = "power-forecast-private-${count.index}"
  }
}

resource "aws_route_table" "private_route_table" {
  count  = length(var.azs)
  vpc_id = aws_vpc.vpc.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = var.enable_nat_gateway ? aws_nat_gateway.nat_gateways[count.index].id : null # 外向き通信をNAT経由にする
  }
  tags = {
    Name = "power-forecast-private-route-${count.index}"
  }
}

resource "aws_route_table_association" "private_route_table_associations" {
  count          = length(var.azs)
  subnet_id      = aws_subnet.private_subnet[count.index].id
  route_table_id = aws_route_table.private_route_table[count.index].id
}


output "vpc_id" {
  value = aws_vpc.vpc.id
}

output "private_subnet_ids" {
  value = aws_subnet.private_subnet[*].id
}

output "public_subnet_ids" {
  value = aws_subnet.public_subnet[*].id
}
